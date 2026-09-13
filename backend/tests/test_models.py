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


def test_runner_includes_stderr_when_child_writes_no_result(tmp_path):
    async def scenario():
        settings = Settings()
        settings.cache_dir = tmp_path
        runner = LocalRunner(settings)
        process = SimpleNamespace(returncode=1)

        async def wait():
            return 1

        process.wait, process.kill = wait, lambda: None

        async def spawn(*_args, **kwargs):
            kwargs["stderr"].write(
                b"Traceback (most recent call last):\nModuleNotFoundError: No module named 'llama_cpp'\n"
            )
            kwargs["stderr"].flush()
            return process

        with (
            patch.object(
                runner.hub,
                "resolve",
                return_value={
                    "snapshot": str(tmp_path),
                    "revision": "abc",
                    "fingerprint": "x",
                },
            ),
            patch("asyncio.create_subprocess_exec", side_effect=spawn),
            pytest.raises(RuntimeError, match="llama_cpp"),
        ):
            await runner.run("fast", {}, "job")

    asyncio.run(scenario())


def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_OVERLAY", str(tmp_path / "models.local.yaml"))
    settings = Settings()
    settings.cache_dir = tmp_path / "models"
    return settings


def test_overlay_merges_over_profile(tmp_path, monkeypatch):
    overlay = tmp_path / "models.local.yaml"
    overlay.write_text(yaml.safe_dump({"models": {"fast": {"revision": "abc"}}}))
    monkeypatch.setenv("MODEL_OVERLAY", str(overlay))
    settings = Settings()
    assert settings.models.models["fast"].revision == "abc"
    assert settings.model_overrides == {"models": {"fast": {"revision": "abc"}}}
    assert settings.override_for("fast") == {"revision": "abc"}
    assert settings.override_for("quality") == {}


def test_overlay_rejects_non_overridable_fields(tmp_path, monkeypatch):
    overlay = tmp_path / "models.local.yaml"
    overlay.write_text(yaml.safe_dump({"models": {"fast": {"runtime": "kokoro"}}}))
    monkeypatch.setenv("MODEL_OVERLAY", str(overlay))
    with pytest.raises(ValueError, match="non-overridable"):
        Settings()


def test_save_and_reset_override_roundtrip(tmp_path, monkeypatch):
    settings = _isolated(tmp_path, monkeypatch)
    default_layers = settings.models.models["fast"].gpu_layers
    settings.save_override("fast", {"gpu_layers": 8})
    assert settings.models.models["fast"].gpu_layers == 8
    assert settings.model_overlay_path.exists()
    reloaded = Settings()
    assert reloaded.models.models["fast"].gpu_layers == 8
    settings.save_override("fast", {"revision": "pinned"})
    assert settings.override_for("fast") == {"gpu_layers": 8, "revision": "pinned"}
    settings.reset_override("fast")
    assert settings.models.models["fast"].gpu_layers == default_layers
    assert not settings.model_overlay_path.exists()
    assert Settings().override_for("fast") == {}


def test_invalid_override_rejected_and_nothing_written(tmp_path, monkeypatch):
    settings = _isolated(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="CPU"):
        settings.save_override("embeddings", {"device": "cuda"})
    assert not settings.model_overlay_path.exists()
    assert settings.models.models["embeddings"].device == "cpu"
    with pytest.raises(KeyError):
        settings.save_override("nope", {"revision": "x"})


def _run(coroutine):
    return asyncio.run(coroutine)


def test_setup_manager_scrubs_token_and_rejects_unknown_extra(tmp_path, monkeypatch):
    import sys

    from app.models.setup import SetupManager

    monkeypatch.setenv("HF_TOKEN", "hf_secretvalue123")
    calls = []

    def factory(extra):
        calls.append(extra)
        return [
            sys.executable,
            "-c",
            "import os; print('token', os.environ.get('HF_TOKEN'), 'hf_abcdefghij')",
        ]

    manager = SetupManager(ModelHub(tmp_path), root=tmp_path, command_factory=factory)
    with pytest.raises(ValueError, match="Unknown runtime extra"):
        manager.start_install("shell")

    async def scenario():
        snapshot = manager.start_install("llm")
        assert snapshot["state"] == "running"
        assert manager.any_running()
        with pytest.raises(RuntimeError, match="already running"):
            manager.start_install("llm")
        await manager._jobs["install:llm"]
        return manager.status("install:llm")

    status = _run(scenario())
    assert calls == ["llm"]
    assert status["state"] == "done"
    assert status["ended_at"]
    joined = "\n".join(status["log"])
    assert "hf_secretvalue123" not in joined
    assert "hf_abcdefghij" not in joined
    assert "token None ***" in joined  # HF_TOKEN stripped from the child env


def test_setup_manager_download_states(tmp_path):
    import threading

    from app.models.setup import SetupBusy, SetupManager

    spec = Settings().models.models["fast"]
    hub = ModelHub(tmp_path)
    release = threading.Event()

    def blocking_download(spec):
        release.wait(5)
        return {"revision": "c" * 40}

    async def scenario():
        with patch.object(hub, "download", side_effect=blocking_download):
            manager = SetupManager(hub, root=tmp_path)
            manager.start_download("fast", spec)
            with pytest.raises(SetupBusy):
                manager.start_download("fast", spec)
            release.set()
            await manager._jobs["download:fast"]
            done = manager.status("download:fast")
        with patch.object(
            hub, "download", side_effect=ModelNotReady("hf_deadbeef00 missing")
        ):
            manager.start_download("fast", spec)
            await manager._jobs["download:fast"]
            failed = manager.status("download:fast")
        return done, failed

    done, failed = _run(scenario())
    assert done["state"] == "done"
    assert done["log"][-1].startswith("Downloaded ")
    assert failed["state"] == "failed"
    assert failed["error"] == "*** missing"
