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
log = logging.getLogger(__name__)


class RenderError(ValueError):
    pass


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def timeline(scenes: list[dict], alignment: dict, duration: float) -> list[dict]:
    """Use aligned word starts; reject mismatched text instead of guessing timing."""
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
            scenes = Storyboard.model_validate(
                {"scenes": outputs["storyboard"]["scenes"]}
            ).model_dump()["scenes"]
            audio = artifacts.resolve(job["id"], outputs["narration"]["audio"]["id"])
            with wave.open(str(audio)) as wav:
                duration = wav.getnframes() / wav.getframerate()
            scenes = timeline(scenes, outputs["alignment"], duration)
        except (KeyError, ValueError, wave.Error) as exc:
            raise RenderError(
                f"Remotion/FFmpeg needs valid storyboard, narration and alignment: {exc}"
            ) from exc
        with tempfile.TemporaryDirectory(dir=artifacts.folder(job["id"])) as temporary:
            folder = Path(temporary).resolve()
            media = folder / "media"
            media.mkdir()
            shutil.copyfile(audio, media / "narration.wav")
            assets = outputs.get("assets", {})
            for scene in scenes:
                if scene["component"] == "ImagePan":
                    match = next(
                        (
                            a
                            for a in assets.get("images", [])
                            if a["scene_id"] == scene["scene_id"]
                        ),
                        None,
                    )
                    if not match:
                        raise RenderError("Missing generated scene image")
                    source = artifacts.resolve(job["id"], match["artifact"]["id"])
                    name = scene["scene_id"] + source.suffix
                    shutil.copyfile(source, media / name)
                    scene["image"] = name
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
                    data, _, _, filename = await library.content(
                        job["series_id"], match["asset_id"]
                    )
                    if hashlib.sha256(data).hexdigest() != match["sha256"]:
                        raise RenderError("Series asset hash changed")
                    name = scene["scene_id"] + Path(filename).suffix
                    (media / name).write_bytes(data)
                    scene["image"] = name
            payload = {
                "scenes": scenes,
                "audio": "narration.wav",
                "durationInFrames": math.ceil(duration * FPS),
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
                "renderer": "remotion",
            }
