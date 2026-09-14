import asyncio
import wave
from unittest.mock import AsyncMock

import pytest

from app.artifacts import Artifacts
from app.rendering import RemotionRenderer, RenderError, timeline


def scene(text="Hello world", number=1):
    return {
        "scene_id": f"scene_{number:03d}",
        "component": "DefinitionCard",
        "props": {"title": "Hello", "body": "World"},
        "narration_text": text,
        "duration_seconds": 2,
    }


def test_timeline_uses_alignment_and_keeps_audio_tail():
    scenes = [scene("Hello", 1), scene("world", 2)]
    result = timeline(
        scenes,
        {
            "segments": [
                {
                    "start": 0.2,
                    "end": 1.5,
                    "text": "Hello world",
                    "words": [
                        {"word": "Hello", "start": 0.2, "end": 0.5},
                        {"word": "world", "start": 1, "end": 1.5},
                    ],
                }
            ]
        },
        2,
    )
    assert [(s["from"], s["frames"]) for s in result] == [(0, 30), (30, 30)]


@pytest.mark.parametrize(
    "segment",
    [
        {"text": "Wrong words", "start": 0, "end": 1},
        {"text": "Hello world", "start": -1, "end": 1},
        {"text": "Hello world", "start": 0, "end": float("nan")},
        {"text": "Hello world", "start": 0, "end": 3},
    ],
)
def test_bad_alignment_fails_closed(segment):
    with pytest.raises(RenderError):
        timeline([scene()], {"segments": [segment]}, 2)


def render_fixture(tmp_path, monkeypatch):
    from app import rendering

    project = tmp_path / "renderer"
    (project / "node_modules/@remotion/renderer").mkdir(parents=True)
    monkeypatch.setattr(rendering, "PROJECT", project)
    monkeypatch.setattr(rendering.shutil, "which", lambda _: "/usr/bin/node")
    artifacts = Artifacts(tmp_path / "artifacts")
    audio = tmp_path / "audio.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 16000)
    outputs = {
        "storyboard": {"scenes": [scene()]},
        "narration": {"audio": artifacts.adopt("job", audio)},
        "alignment": {"segments": [{"text": "Hello world", "start": 0, "end": 1.5}]},
        "assets": {},
    }
    job = {
        "id": "job",
        "stages": [{"name": k, "output": v} for k, v in outputs.items()],
    }
    return job, artifacts


def test_render_adopts_only_successful_output(tmp_path, monkeypatch):
    job, artifacts = render_fixture(tmp_path, monkeypatch)

    async def spawn(*args, **kwargs):
        from pathlib import Path

        assert "HF_TOKEN" not in kwargs["env"]
        Path(args[-1]).write_bytes(b"test-mp4" * 10)
        return type(
            "Process", (), {"returncode": 0, "wait": AsyncMock(return_value=0)}
        )()

    monkeypatch.setenv("HF_TOKEN", "test-secret")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    result = asyncio.run(RemotionRenderer().render(job, artifacts, None))
    assert artifacts.resolve("job", result["video"]["id"]).suffix == ".mp4"
    assert result["timeline"][0]["frames"] == 60


def test_failed_process_never_returns_video(tmp_path, monkeypatch):
    job, artifacts = render_fixture(tmp_path, monkeypatch)
    process = type(
        "Process", (), {"returncode": 1, "wait": AsyncMock(return_value=1)}
    )()
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", AsyncMock(return_value=process)
    )
    with pytest.raises(RenderError, match="render failed"):
        asyncio.run(RemotionRenderer().render(job, artifacts, None))
    assert not list(artifacts.folder("job").glob("*.mp4"))


def test_missing_image_stops_before_process(tmp_path, monkeypatch):
    job, artifacts = render_fixture(tmp_path, monkeypatch)
    job["stages"][0]["output"]["scenes"][0].update(
        component="ImagePan", props={"title": "Image", "prompt": "A valid image prompt"}
    )
    spawn = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(RenderError, match="Missing generated"):
        asyncio.run(RemotionRenderer().render(job, artifacts, None))
    spawn.assert_not_called()


def test_series_asset_hash_mismatch_stops_render(tmp_path, monkeypatch):
    job, artifacts = render_fixture(tmp_path, monkeypatch)
    job["series_id"] = "series"
    job["stages"][0]["output"]["scenes"][0].update(
        component="SeriesAsset", props={"title": "Logo", "asset_id": "asset"}
    )
    job["stages"][3]["output"]["series_assets"] = [
        {"scene_id": "scene_001", "asset_id": "asset", "sha256": "incorrect"}
    ]
    library = type(
        "Library",
        (),
        {
            "content": AsyncMock(
                return_value=(b"image", "image/png", "logo", "hash.png")
            )
        },
    )()
    with pytest.raises(RenderError, match="hash changed"):
        asyncio.run(RemotionRenderer().render(job, artifacts, library))


def test_cancellation_kills_process_group_and_cleans_temp(tmp_path, monkeypatch):
    from app import rendering

    job, artifacts = render_fixture(tmp_path, monkeypatch)
    process = type(
        "Process",
        (),
        {"pid": 12345, "wait": AsyncMock(side_effect=[asyncio.CancelledError(), 0])},
    )()
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", AsyncMock(return_value=process)
    )
    killed = []
    monkeypatch.setattr(rendering.os, "killpg", lambda pid, sig: killed.append(pid))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(RemotionRenderer().render(job, artifacts, None))
    assert killed == [12345]
    assert all(path.is_file() for path in artifacts.folder("job").iterdir())


def test_visual_reveals_leave_reading_time_and_support_random_access():
    """Exercise the renderer's actual JS timing without a browser or network."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed to check renderer animation timing")
    module = Path(__file__).resolve().parents[2] / "renderer/src/motion.mjs"
    subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
import assert from 'node:assert/strict';
import {{revealAt}} from {json.dumps(module.as_uri())};
for (const frames of [30, 120, 1200]) {{
  for (const count of [1, 3, 6, 8]) {{
    for (let index = 0; index < count; index++) {{
      assert.equal(revealAt(-1, frames, index, count), 0);
      assert.equal(revealAt(frames * .8, frames, index, count), 1);
      const middle = revealAt(frames * .4, frames, index, count);
      revealAt(frames, frames, index, count);
      assert.equal(revealAt(frames * .4, frames, index, count), middle);
      assert.ok(middle >= 0 && middle <= 1);
    }}
    assert.ok(revealAt(frames * .2, frames, 0, count) >=
              revealAt(frames * .2, frames, count - 1, count));
  }}
}}
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_word_timeline_and_manifest_carry_chapters_plates_and_captions(
    tmp_path, monkeypatch
):
    """The manifest gives every scene a plate (its own image or the chapter
    hero), positions chapters in frames, and lists caption words."""
    import json
    import shutil
    from pathlib import Path

    from app import rendering
    from app.rendering import word_timeline

    scenes = [
        {
            "scene_id": "scene_001",
            "narration_text": "Names map to addresses.",
            "duration_seconds": 3,
            "component": "DefinitionCard",
            "props": {"title": "DNS", "body": "b"},
        },
        {
            "scene_id": "scene_002",
            "narration_text": "Caches keep it fast.",
            "duration_seconds": 3,
            "component": "Outro",
            "props": {"title": "Recap", "takeaways": ["x"]},
        },
    ]
    segments = [
        {"text": "Names map to addresses.", "start": 0.0, "end": 2.0},
        {"text": "Caches keep it fast.", "start": 2.0, "end": 4.0},
    ]
    words = word_timeline(scenes, {"segments": segments}, 4.0)
    assert [w["text"] for w in words] == [
        "names",
        "map",
        "to",
        "addresses",
        "caches",
        "keep",
        "it",
        "fast",
    ]
    assert words[0] == {"text": "names", "from": 0, "frames": 15, "scene": 0}
    assert words[4]["scene"] == 1 and words[-1]["from"] + words[-1]["frames"] == 120

    artifacts = Artifacts(tmp_path / "artifacts")
    (tmp_path / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\nhero")
    (tmp_path / "own.png").write_bytes(b"\x89PNG\r\n\x1a\nown")
    (tmp_path / "tone.wav").write_bytes(b"")
    import wave

    with wave.open(str(tmp_path / "tone.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 32000)
    audio = artifacts.adopt("job", tmp_path / "tone.wav")
    hero = artifacts.adopt("job", tmp_path / "hero.png")
    own = artifacts.adopt("job", tmp_path / "own.png")
    job = {
        "id": "job",
        "title": "DNS",
        "render": {"captions": False},
        "stages": [
            {
                "name": "storyboard",
                "output": {
                    "scenes": scenes,
                    "chapters": [
                        {
                            "chapter_id": "chapter_01",
                            "title": "Basics",
                            "tagline": "t",
                            "first_scene": "scene_001",
                            "last_scene": "scene_002",
                            "hero_prompt": "a hero illustration",
                            "accent": 3,
                        }
                    ],
                },
            },
            {"name": "narration", "output": {"audio": audio}},
            {"name": "alignment", "output": {"segments": segments}},
            {
                "name": "assets",
                "output": {
                    "images": [
                        {"id": "chapter_01", "kind": "hero", "artifact": hero},
                        {"id": "scene_002", "kind": "scene", "artifact": own},
                        {
                            "id": "scene_001",
                            "kind": "scene",
                            "fallback": "chapter_hero",
                        },
                    ]
                },
            },
        ],
    }
    project = tmp_path / "renderer"
    (project / "node_modules/@remotion/renderer").mkdir(parents=True)
    monkeypatch.setattr(rendering, "PROJECT", project)
    monkeypatch.setattr(rendering.shutil, "which", lambda _: "/usr/bin/node")
    captured = {}

    async def fake_exec(*args, **kwargs):
        manifest = Path(args[2])
        captured["payload"] = json.loads(manifest.read_text())
        captured["media"] = sorted(p.name for p in Path(args[3]).iterdir())
        Path(args[4]).write_bytes(b"0" * 64)

        class Process:
            pid = 1
            returncode = 0

            async def wait(self):
                return 0

        return Process()

    monkeypatch.setattr(rendering.asyncio, "create_subprocess_exec", fake_exec)
    result = asyncio.run(RemotionRenderer().render(job, artifacts, None))
    payload = captured["payload"]
    assert payload["captions"] is False and payload["introFrames"] == 0
    assert payload["music"] is None and payload["brand"] == {
        "name": None,
        "palette": [],
    }
    assert [s["plate"] for s in payload["scenes"]] == [
        "chapter_01.png",
        "scene_002.png",
    ]
    assert payload["chapters"][0]["image"] == "chapter_01.png"
    assert (
        payload["chapters"][0]["from"] == 0 and payload["chapters"][0]["frames"] == 120
    )
    assert [s["chapter"] for s in payload["scenes"]] == [0, 0]
    assert len(payload["words"]) == 8 and payload["durationInFrames"] == 120
    assert {"chapter_01.png", "scene_002.png", "narration.wav", "fonts"} <= set(
        captured["media"]
    )
    assert result["chapters"][0]["title"] == "Basics" and result["captions"] is False
    shutil.rmtree(project)


def test_renderer_motion_and_highlight_helpers_are_deterministic():
    """Transitions, counters, captions and the code tokenizer run in Node
    without a browser: pure functions of the frame."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed to check renderer helpers")
    src = Path(__file__).resolve().parents[2] / "renderer/src"
    subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
import assert from 'node:assert/strict';
import {{OVERLAP, handover, pickTransition, counter, typewriter, captionAt, musicGain, speechDensity}} from {json.dumps((src / "motion.mjs").as_uri())};
import {{tokenize, LANGUAGES}} from {json.dumps((src / "highlight.mjs").as_uri())};
// Handover: fully entered after OVERLAP frames, exits only over the last OVERLAP.
assert.deepEqual(handover(0, 100, false), {{enter: 0, exit: 0}});
assert.deepEqual(handover(OVERLAP, 100, false), {{enter: 1, exit: 0}});
assert.equal(handover(100 + OVERLAP, 100, false).exit, 1);
assert.equal(handover(100 + OVERLAP, 100, true).exit, 0);
// Chapter boundaries always wipe; other cuts are stable per (chapter, scene).
assert.equal(pickTransition(2, 5, true), 'chapter');
assert.equal(pickTransition(2, 5, false), pickTransition(2, 5, false));
assert.ok(['dissolve','slide','wipe'].includes(pickTransition(0, 1, false)));
// Counter settles on the target and never overshoots.
assert.equal(counter(0, 300, 120), 0);
assert.equal(counter(300, 300, 120), 120);
assert.ok(counter(30, 300, 120) > 0 && counter(30, 300, 120) < 120);
assert.equal(typewriter(10, 0, 5, 1), 5);
assert.equal(typewriter(-1, 0, 5, 1), 0);
// Captions: only this scene's words, current word tracked, at most 8 per line.
const words = [];
for (let i = 0; i < 20; i++) words.push({{text: 'w' + i, from: i * 10, frames: 10, scene: i < 12 ? 0 : 1}});
assert.equal(captionAt(words, 0, 75).line.length, 8);
const c = captionAt(words, 0, 95);
assert.equal(c.active.text, 'w9');
assert.equal(c.line.length, 4);
assert.equal(captionAt(words, 1, 125).active.text, 'w12');
assert.equal(captionAt(words, 3, 0), null);
// Music ducks under speech, fades at both ends, stays deterministic.
assert.ok(speechDensity(words, 50) > speechDensity(words, 5000));
assert.ok(musicGain(words, 50, 1000) < musicGain(words, 500, 1000));
assert.equal(musicGain(words, 0, 1000), 0);
assert.equal(musicGain(words, 1000, 1000), 0);
assert.equal(musicGain(words, 500, 1000), musicGain(words, 500, 1000));
// Tokenizer: keywords/strings/comments/numbers, never evaluation.
assert.ok(LANGUAGES.includes('python') && LANGUAGES.includes('text'));
const py = tokenize('return "x"  # note 42', 'python');
assert.deepEqual(py.map(t => t.type), ['keyword','plain','string','plain','comment']);
assert.equal(tokenize('SELECT 1', 'sql')[0].type, 'keyword');
assert.equal(tokenize('alert(1)', 'text').every(t => t.type !== 'keyword'), true);
assert.equal(tokenize('', 'go').length, 0);
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_real_render_covers_every_component(tmp_path):
    """One short real Remotion/Chrome render with all 14 components. Skips
    when `make setup-renderer` has not been run; never downloads anything."""
    import shutil

    from app import render_sample
    from app.artifacts import Artifacts
    from app.rendering import PROJECT

    if (
        not shutil.which("node")
        or not (PROJECT / "node_modules/@remotion/renderer").is_dir()
    ):
        pytest.skip("Renderer packages are not installed")
    if not any((PROJECT / "node_modules/.remotion").glob("**/chrome-headless-shell*")):
        pytest.skip("Chrome Headless Shell is not installed")
    artifacts = Artifacts(tmp_path / "artifacts")
    scenes, segments = [], []
    for index, (component, props) in enumerate(render_sample.SCENES):
        text = f"Scene {index + 1} shows {props['title'].lower()}."
        scenes.append(
            {
                "scene_id": f"scene_{index + 1:03d}",
                "narration_text": text,
                "duration_seconds": 1,
                "component": component,
                "props": props,
            }
        )
        segments.append({"text": text, "start": index, "end": index + 1})
    plate = tmp_path / "plate.png"
    render_sample.gradient_png(plate, (30, 60, 90), 64, 36)
    image = artifacts.adopt("smoke", plate)
    tone = tmp_path / "tone.wav"
    with wave.open(str(tone), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000 * len(scenes))
    job = {
        "id": "smoke",
        "title": "Smoke",
        "stages": [
            {
                "name": "storyboard",
                "output": {
                    "scenes": scenes,
                    "chapters": [
                        {
                            "chapter_id": "chapter_01",
                            "title": "One",
                            "tagline": "",
                            "first_scene": "scene_001",
                            "last_scene": "scene_004",
                            "hero_prompt": "a hero plate",
                            "accent": 0,
                        },
                        {
                            "chapter_id": "chapter_02",
                            "title": "Two",
                            "tagline": "t",
                            "first_scene": "scene_005",
                            "last_scene": scenes[-1]["scene_id"],
                            "hero_prompt": "a hero plate",
                            "accent": 1,
                        },
                    ],
                },
            },
            {"name": "narration", "output": {"audio": artifacts.adopt("smoke", tone)}},
            {"name": "alignment", "output": {"segments": segments}},
            {
                "name": "assets",
                "output": {
                    "images": [
                        {"id": "chapter_01", "kind": "hero", "artifact": image},
                        {"id": "chapter_02", "kind": "hero", "artifact": image},
                        {"id": "scene_012", "kind": "scene", "artifact": image},
                    ]
                },
            },
        ],
    }
    result = asyncio.run(RemotionRenderer().render(job, artifacts, None))
    video = artifacts.resolve("smoke", result["video"]["id"])
    assert video.stat().st_size > 10_000
    assert result["duration_seconds"] == len(scenes)
    assert [c["chapter_id"] for c in result["chapters"]] == ["chapter_01", "chapter_02"]
