"""Fixed Remotion compositions over validated, local job artifacts."""

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import shutil
import signal
import tempfile
import wave
from pathlib import Path

from .schemas import Storyboard

PROJECT = Path(__file__).resolve().parents[2] / "renderer"
FPS = 30
# Brand intro plate before the first scene (only when the series has a logo or
# intro asset); narration and every scene shift by this many frames.
INTRO_FRAMES = 75
# Vendored through the renderer's lockfile; copied next to the media so the
# composition loads them from the loopback asset server, never the network.
FONT_FILES = {
    "inter": [
        "inter-latin-400-normal.woff2",
        "inter-latin-500-normal.woff2",
        "inter-latin-600-normal.woff2",
        "inter-latin-700-normal.woff2",
        "inter-latin-800-normal.woff2",
    ],
    "jetbrains-mono": [
        "jetbrains-mono-latin-400-normal.woff2",
        "jetbrains-mono-latin-600-normal.woff2",
    ],
}
log = logging.getLogger(__name__)


class RenderError(ValueError):
    pass


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def timed_words(scenes: list[dict], alignment: dict, duration: float) -> list[tuple]:
    """(token, start_seconds) for every narrated word, in storyboard order.
    Uses aligned word starts; rejects mismatched text instead of guessing."""
    timed = []
    previous = 0.0
    for segment in alignment.get("segments", []):
        for item in segment.get("words") or [segment]:
            tokens = words(item.get("word", item.get("text", "")))
            start, end = item["start"], item["end"]
            if not tokens or not all(math.isfinite(v) for v in (start, end)):
                raise RenderError("Invalid alignment timestamps")
            if start < previous or end <= start or end > duration + 0.1:
                raise RenderError("Alignment timestamps exceed narration or overlap")
            timed.extend(
                (token, start + (end - start) * i / len(tokens))
                for i, token in enumerate(tokens)
            )
            previous = end
    expected = [token for scene in scenes for token in words(scene["narration_text"])]
    if not expected or expected != [token for token, _ in timed]:
        raise RenderError("Alignment text does not match storyboard narration")
    return timed


def timeline(scenes: list[dict], alignment: dict, duration: float) -> list[dict]:
    """Contiguous scene frames from aligned word starts; the audio tail stays."""
    timed = timed_words(scenes, alignment, duration)
    starts, cursor = [0], 0
    for scene in scenes[:-1]:
        cursor += len(words(scene["narration_text"]))
        starts.append(round(timed[cursor][1] * FPS))
    ends = starts[1:] + [math.ceil(duration * FPS)]
    if any(end <= start for start, end in zip(starts, ends)):
        raise RenderError("Aligned scene has no frames")
    return [
        {**scene, "from": start, "frames": end - start}
        for scene, start, end in zip(scenes, starts, ends)
    ]


def word_timeline(scenes: list[dict], alignment: dict, duration: float) -> list[dict]:
    """Caption words as {text, from, frames, scene} in frames. Each word lasts
    until the next word starts; the last until the audio ends."""
    timed = timed_words(scenes, alignment, duration)
    total = math.ceil(duration * FPS)
    result, cursor = [], 0
    for index, scene in enumerate(scenes):
        for _ in words(scene["narration_text"]):
            start = round(timed[cursor][1] * FPS)
            nxt = round(timed[cursor + 1][1] * FPS) if cursor + 1 < len(timed) else total
            result.append(
                {
                    "text": timed[cursor][0],
                    "from": start,
                    "frames": max(1, nxt - start),
                    "scene": index,
                }
            )
            cursor += 1
    return result


def font_sources() -> list[Path]:
    """Font files from the renderer's installed packages (make setup-renderer)."""
    return [
        PROJECT / "node_modules/@fontsource" / package / "files" / name
        for package, names in FONT_FILES.items()
        for name in names
    ]


def series_brand(job: dict) -> dict:
    """Name and palette from the job's series snapshot; empty for standalone jobs."""
    context = job.get("series_context") or {}
    visual = (context.get("guidance") or {}).get("visual") or {}
    return {
        "name": (context.get("series") or {}).get("name"),
        "palette": visual.get("palette") or [],
    }


class RemotionRenderer:
    async def render(self, job: dict, artifacts, library) -> dict:
        """Render H.264/AAC, then adopt the completed MP4 into the job store."""
        if (
            not shutil.which("node")
            or not (PROJECT / "node_modules/@remotion/renderer").exists()
        ):
            raise RenderError(
                "Remotion/FFmpeg is not connected: run make setup-renderer"
            )
        outputs = {stage["name"]: stage["output"] or {} for stage in job["stages"]}
        try:
            board = Storyboard.model_validate(
                {
                    "scenes": outputs["storyboard"]["scenes"],
                    "chapters": outputs["storyboard"].get("chapters") or [],
                }
            ).model_dump()
            audio = artifacts.resolve(job["id"], outputs["narration"]["audio"]["id"])
            with wave.open(str(audio)) as wav:
                duration = wav.getnframes() / wav.getframerate()
            scenes = timeline(board["scenes"], outputs["alignment"], duration)
            timed = word_timeline(board["scenes"], outputs["alignment"], duration)
        except (KeyError, ValueError, wave.Error) as exc:
            raise RenderError(
                f"Remotion/FFmpeg needs valid storyboard, narration and alignment: {exc}"
            ) from exc
        # Storyboards planned before chapters existed render as one chapter.
        board_chapters = board["chapters"] or [
            {
                "chapter_id": "chapter_01",
                "title": job.get("title", ""),
                "tagline": "",
                "first_scene": scenes[0]["scene_id"],
                "last_scene": scenes[-1]["scene_id"],
                "accent": 0,
            }
        ]
        options = job.get("render") or {}
        with tempfile.TemporaryDirectory(dir=artifacts.folder(job["id"])) as temporary:
            folder = Path(temporary).resolve()
            media = folder / "media"
            (media / "fonts").mkdir(parents=True)
            for font in font_sources():
                if font.is_file():
                    shutil.copyfile(font, media / "fonts" / font.name)
            shutil.copyfile(audio, media / "narration.wav")
            assets = outputs.get("assets", {})
            images = {
                image.get("id") or image.get("scene_id"): image
                for image in assets.get("images", [])
            }

            def stage_image(image, name):
                if not image or "artifact" not in image:
                    return None
                source = artifacts.resolve(job["id"], image["artifact"]["id"])
                target = name + source.suffix
                shutil.copyfile(source, media / target)
                return target

            async def stage_series(pinned, name):
                data, _, _, filename = await library.content(
                    job["series_id"], pinned["asset_id"]
                )
                if hashlib.sha256(data).hexdigest() != pinned["sha256"]:
                    raise RenderError("Series asset hash changed")
                target = name + Path(filename).suffix
                (media / target).write_bytes(data)
                return target

            ids = [scene["scene_id"] for scene in scenes]
            chapters = []
            for index, chapter in enumerate(board_chapters):
                try:
                    first = ids.index(chapter["first_scene"])
                    last = ids.index(chapter["last_scene"])
                except ValueError as exc:
                    raise RenderError("Storyboard chapters do not match scenes") from exc
                chapters.append(
                    {
                        **chapter,
                        "index": index,
                        "from": scenes[first]["from"],
                        "frames": sum(s["frames"] for s in scenes[first : last + 1]),
                        "image": stage_image(
                            images.get(chapter["chapter_id"]), chapter["chapter_id"]
                        ),
                    }
                )
                for scene in scenes[first : last + 1]:
                    scene["chapter"] = index
            if any("chapter" not in scene for scene in scenes):
                raise RenderError("Storyboard chapters do not cover every scene")
            for scene in scenes:
                hero = chapters[scene["chapter"]]["image"]
                own = stage_image(images.get(scene["scene_id"]), scene["scene_id"])
                scene["plate"] = own or hero
                if scene["component"] == "ImagePan":
                    if not scene["plate"]:
                        raise RenderError("Missing generated scene image")
                    scene["image"] = scene["plate"]
                elif scene["component"] == "SeriesAsset":
                    match = next(
                        (
                            a
                            for a in assets.get("series_assets", [])
                            if a["scene_id"] == scene["scene_id"]
                            and a["asset_id"] == scene["props"]["asset_id"]
                        ),
                        None,
                    )
                    if not match:
                        raise RenderError("Missing pinned series asset")
                    scene["image"] = await stage_series(match, scene["scene_id"])
            brand = series_brand(job)
            for kind, pinned in (assets.get("brand") or {}).items():
                brand[kind] = await stage_series(pinned, f"brand_{kind}")
            music = None
            if assets.get("music"):
                music = await stage_series(assets["music"], "music")
            intro_frames = INTRO_FRAMES if brand.get("intro") or brand.get("logo") else 0
            if intro_frames:
                for item in (*scenes, *chapters, *timed):
                    item["from"] += intro_frames
            payload = {
                "scenes": scenes,
                "chapters": chapters,
                "words": timed,
                "audio": "narration.wav",
                "music": music,
                "brand": brand,
                "captions": bool(options.get("captions", True)),
                "introFrames": intro_frames,
                "durationInFrames": math.ceil(duration * FPS) + intro_frames,
            }
            manifest = folder / "props.json"
            manifest.write_text(json.dumps(payload))
            output = folder / "video.mp4"
            # An allowlist prevents inference/auth secrets reaching Node or Chrome.
            env = {
                key: os.environ[key]
                for key in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT")
                if key in os.environ
            }
            with tempfile.TemporaryFile() as diagnostics:
                process = await asyncio.create_subprocess_exec(
                    "node",
                    str(PROJECT / "render.mjs"),
                    str(manifest),
                    str(media),
                    str(output),
                    cwd=PROJECT,
                    env=env,
                    start_new_session=True,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=diagnostics,
                )
                try:
                    await asyncio.wait_for(process.wait(), timeout=7200)
                except (asyncio.CancelledError, TimeoutError):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.wait()
                    raise
                diagnostics.seek(0, 2)
                diagnostics.seek(max(0, diagnostics.tell() - 4000))
                error = diagnostics.read().decode(errors="replace")
            if process.returncode or not output.is_file() or output.stat().st_size < 32:
                log.error("Remotion/FFmpeg exited %s: %s", process.returncode, error)
                raise RenderError(
                    "Remotion/FFmpeg render failed; check renderer dependencies with make setup-renderer"
                )
            return {
                "video": artifacts.adopt(job["id"], output),
                "duration_seconds": duration,
                "fps": FPS,
                "width": 1920,
                "height": 1080,
                "codec": "h264",
                "audio_codec": "aac",
                "timeline": scenes,
                "chapters": chapters,
                "captions": payload["captions"],
                "music": bool(music),
                "intro_frames": intro_frames,
                "renderer": "remotion",
            }
