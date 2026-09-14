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
