import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from app.config import ROOT, ModelConfig, ModelSpec, Settings
from app.models.gpu import GPUManager
from app.models.hub import ModelHub, ModelNotReady
from app.models.runner import LocalRunner


def test_config_rejects_wrong_stage_runtime():
    config = Settings().models.model_dump()
    config["routes"]["narration"] = "fast"
    with pytest.raises(ValueError, match="kokoro"):
        ModelConfig.model_validate(config)


def test_device_and_runtime_rules():
    base = Settings().models.model_dump()
    fast = base["models"]["fast"]
    assert ModelConfig.model_validate(
        {**base, "models": {**base["models"], "fast": {**fast, "device": "metal"}}}
    )
    with pytest.raises(ValueError, match="metal"):
        ModelSpec.model_validate({**base["models"]["alignment"], "device": "metal"})
    with pytest.raises(ValueError, match="cuda"):
        ModelSpec.model_validate({**base["models"]["images"], "device": "cpu"})
    with pytest.raises(ValueError, match="extra_repos"):
        ModelSpec.model_validate({**base["models"]["images"], "extra_repos": []})
    enabled = {**base, "images_enabled": True}
    assert ModelConfig.model_validate(enabled).models["images"].runtime == (
        "diffusers_gguf"
    )
    swapped = {
        **base,
        "models": {
            **base["models"],
            "narration": {
                "runtime": "qwen_tts",
                "repo_id": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
                "files": ["*.safetensors"],
                "device": "cuda",
            },
            "alignment": {
                "runtime": "ctc_aligner",
                "repo_id": "MahmoudAshraf/mms-300m-1130-forced-aligner",
                "files": ["*.safetensors"],
            },
        },
    }
    assert ModelConfig.model_validate(swapped).routes["alignment"] == "alignment"
    with pytest.raises(ValueError, match="kokoro or qwen_tts"):
        ModelConfig.model_validate(
            {**base, "routes": {**base["routes"], "narration": "alignment"}}
        )


def test_hardware_profiles_validate():
    for name in ("models.mac.yaml", "models.cuda-8gb.yaml"):
        data = yaml.safe_load((ROOT / "config" / name).read_text())
        config = ModelConfig.model_validate(data)
        assert config.models["quality"].gpu_layers == -1
    assert config.images_enabled
    assert config.governor.critique_rounds == 3


def test_hub_downloads_and_verifies_extra_repos(tmp_path):
    spec = Settings().models.models["images"]
    hub = ModelHub(tmp_path)
    snapshots = {}
    for repo in [spec, *spec.extra_repos]:
        folder = tmp_path / repo.repo_id.replace("/", "__")
        folder.mkdir()
        (folder / (repo.filename or "model_index.json")).write_bytes(b"x")
        snapshots[repo.repo_id] = str(folder)
    with (
        patch("app.models.hub.HfApi") as api,
        patch(
            "app.models.hub.snapshot_download",
            side_effect=lambda repo_id, **kwargs: snapshots[repo_id],
        ),
    ):
        api.return_value.model_info.return_value.sha = "b" * 40
        manifest = hub.download(spec)
    assert set(manifest["extras"]) == {"text_encoder", "base"}
    assert (
        manifest["extras"]["text_encoder"]["filename"] == spec.extra_repos[0].filename
    )
    assert hub.resolve(spec) == manifest
    Path(manifest["extras"]["base"]["snapshot"], "model_index.json").unlink()
    with pytest.raises(ModelNotReady, match="incomplete"):
        hub.resolve(spec)


def test_hub_pins_commit_and_detects_missing_cache(tmp_path):
    spec = Settings().models.models["fast"]
    hub = ModelHub(tmp_path)
    with pytest.raises(ModelNotReady):
        hub.resolve(spec)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / spec.filename).write_bytes(b"test-gguf")
    with (
        patch("app.models.hub.HfApi") as api,
        patch(
            "app.models.hub.snapshot_download", return_value=str(snapshot)
        ) as download,
    ):
        api.return_value.model_info.return_value.sha = "a" * 40
        manifest = hub.download(spec)
        assert manifest["revision"] == "a" * 40
        assert download.call_args.kwargs["revision"] == "a" * 40
        assert download.call_args.kwargs["allow_patterns"] == spec.files
        assert hub.resolve(spec) == manifest
    (snapshot / spec.filename).unlink()
    with pytest.raises(ModelNotReady, match="incomplete"):
        hub.resolve(spec)


def test_gpu_priority_timeout_cancellation_and_cleanup():
    async def scenario():
        gpu = GPUManager()
        seen = []

        async def work(name, priority):
            async with gpu.acquire(name, priority, 1, {"job_id": name}):
                seen.append(name)

        async with gpu.acquire("active"):
            low = asyncio.create_task(work("low", 40))
            high = asyncio.create_task(work("high", 1))
            cancelled = asyncio.create_task(work("cancelled", 0))
            await asyncio.sleep(0)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled
            with pytest.raises(TimeoutError):
                async with gpu.acquire("timeout", timeout=0.01):
                    pass
        await asyncio.gather(low, high)
        assert seen == ["high", "low"]

        async def cleanup():
            seen.append("unloaded")

        with pytest.raises(RuntimeError):
            async with gpu.acquire("broken", unload=cleanup):
                raise RuntimeError("failed")
        assert seen[-1] == "unloaded"
        assert gpu.status() == {"active": None, "queued": []}

    asyncio.run(scenario())


def test_runner_kills_child_on_timeout_and_releases_lock(tmp_path):
    async def scenario():
        settings = Settings()
        settings.cache_dir = tmp_path
        settings.models.models["fast"].timeout_seconds = 0.01
        runner = LocalRunner(settings)
        process = SimpleNamespace(returncode=None, killed=False)

        async def wait():
            if process.killed:
                process.returncode = -9
                return -9
            await asyncio.sleep(60)

        def kill():
            process.killed = True

        process.wait, process.kill = wait, kill
        with (
            patch.object(
                runner.hub, "resolve", return_value={"snapshot": str(tmp_path)}
            ),
            patch("asyncio.create_subprocess_exec", return_value=process),
            pytest.raises(TimeoutError),
        ):
            await runner.run("fast", {}, "job")
        assert process.killed
        assert runner.gpu.active is None

    asyncio.run(scenario())
