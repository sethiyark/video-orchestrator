import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from test_pipeline import wait

from app.config import Settings
from app.local_provider import LocalProvider
from app.main import create_app
from app.providers import STAGES
from app.rendering import RenderError
from app.store import Store


class PipelineFixtureRunner:
    async def run(self, role, payload, job_id):
        provenance = {"role": role, "revision": "test-fixture"}
        if role == "narration":
            import wave

            with wave.open(payload["output_path"], "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(24000)
                audio.writeframes(b"\x00\x00" * 24000)
            return {
                "duration_seconds": 1,
                "text": payload["text"],
                "provenance": provenance,
            }
        if role == "alignment":
            assert Path(payload["audio_path"]).exists()
            assert payload["text"]
            return {
                "segments": [{"text": payload["text"], "start": 0, "end": 1}],
                "method": "asr_transcript",
                "fidelity": 0.97,
                "provenance": provenance,
            }
        if role == "embeddings":
            return {"embeddings": [[1.0, 0.0]], "provenance": provenance}
        claim = {
            "id": "c1",
            "text": "DNS maps names to addresses.",
            "source_id": "s1",
            "quote": "DNS maps domain names to IP addresses.",
        }
        results = {
            "Research": {"summary": "DNS basics", "claims": [claim]},
            "Verification": {
                "verdicts": [
                    {
                        "claim_id": "c1",
                        "supported": True,
                        "confidence": 0.98,
                        "reason": "direct evidence",
                    }
                ]
            },
            "Outline": {
                "sections": [
                    {
                        "title": "DNS",
                        "purpose": "explain",
                        "claim_ids": ["c1"],
                        "estimated_seconds": 10,
                    }
                ]
            },
            "ScriptSection": {
                "text": "DNS maps domain names to IP addresses.",
                "claim_ids": ["c1"],
            },
            "Critic": {
                "score": 9.5,
                "issues": [],
                "required_changes": [],
                "optional_changes": [],
            },
            "StoryboardChunk": {
                "scenes": [
                    {
                        "first_sentence": 1,
                        "last_sentence": 1,
                        "component": "DefinitionCard",
                        "props": {"title": "DNS", "body": "Domain name system"},
                    }
                ]
            },
            "Metadata": {
                "title": "DNS explained",
                "description": "DNS basics",
                "tags": ["DNS"],
            },
        }
        return {
            "results": [
                {"result": results[request["schema_name"]]}
                for request in payload["requests"]
            ],
            "provenance": provenance,
        }


def test_local_pipeline_artifacts_and_explicit_render_boundary(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    path = str(tmp_path / "jobs.db")
    provider = LocalProvider(settings, Store(path), PipelineFixtureRunner())
    provider.renderer.render = AsyncMock(
        side_effect=RenderError("Remotion/FFmpeg unavailable in this offline fixture")
    )
    with TestClient(create_app(path, provider, settings)) as client:
        assert (
            client.post("/api/jobs", json={"title": "No evidence"}).status_code == 422
        )
        response = client.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "sources": [
                    {
                        "id": "s1",
                        "url": "https://example.com",
                        "title": "DNS reference",
                        "excerpt": "DNS maps domain names to IP addresses.",
                    }
                ],
            },
        )
        assert response.status_code == 201
        job_id = response.json()["id"]
        assert client.post(f"/api/jobs/{job_id}/run").status_code == 200
        job = wait(client, job_id, "failed")
        assert "Remotion/FFmpeg" in job["error"]
        stages = {stage["name"]: stage for stage in job["stages"]}
        assert stages["metadata"]["status"] == "completed"
        assert stages["upload"]["status"] == "pending"
        assert client.post(f"/api/jobs/{job_id}/approve").status_code == 409
        audio = stages["narration"]["output"]["audio"]
        assert (
            client.get(f"/api/jobs/{job_id}/artifacts/{audio['id']}").content[:4]
            == b"RIFF"
        )
        attempts = client.get(f"/api/jobs/{job_id}/attempts").json()
        assert attempts[-1]["stage"] == "render"
        assert attempts[-1]["status"] == "failed"
        assert len(attempts) == 12  # deterministic unavailable stages are not retried
        assert client.get("/api/models").json()["mode"] == "local"


def test_restart_clears_stages_and_rebases_config_hash(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    path = str(tmp_path / "jobs.db")
    store = Store(path)
    provider = LocalProvider(settings, store, PipelineFixtureRunner())
    with TestClient(create_app(path, provider, settings)) as client:
        job_id = client.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "sources": [
                    {
                        "id": "s1",
                        "url": "https://example.com",
                        "title": "DNS reference",
                        "excerpt": "DNS maps domain names to IP addresses.",
                    }
                ],
            },
        ).json()["id"]
        stored = store.get(job_id)
        stored["config_hash"] = "stale-hash"
        stored["status"] = "failed"
        stored["error"] = "Model configuration changed since this job was created."
        stored["stages"][0]["status"] = "completed"
        stored["stages"][0]["output"] = {"stale": True}
        stored["approved_at"] = "2020-01-01T00:00:00+00:00"
        store.save(stored)
        restarted = client.post(f"/api/jobs/{job_id}/restart")
        assert restarted.status_code == 200
        body = restarted.json()
        assert body["status"] == "queued"
        assert body["config_hash"] == provider.config_hash
        assert body["stage_hashes"] == provider.stage_hashes
        assert body["config_changes"] == []
        assert body["approved_at"] is None
        assert body["error"] is None
        assert all(
            stage["status"] == "pending" and stage["output"] is None
            for stage in body["stages"]
        )
        failed = wait(client, job_id, "failed")
        assert "Remotion/FFmpeg" in failed["error"]


def _local_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_OVERLAY", str(tmp_path / "models.local.yaml"))
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    path = str(tmp_path / "jobs.db")
    store = Store(path)
    provider = LocalProvider(settings, store, PipelineFixtureRunner())
    return settings, provider, create_app(path, provider, settings)


def _poll_setup(client, role, kind):
    for _ in range(200):
        entry = next(
            item
            for item in client.get("/api/models").json()["models"]
            if item["role"] == role
        )
        if entry["setup"][kind]["state"] != "running":
            return entry
        time.sleep(0.02)
    raise AssertionError(f"{kind} for {role} did not finish")


def test_models_endpoint_reports_setup_fields(tmp_path, monkeypatch):
    settings, _, app = _local_client(tmp_path, monkeypatch)
    with TestClient(app) as client:
        body = client.get("/api/models").json()
        assert body["setup_running"] is False
        assert body["overlay_path"] == str(settings.model_overlay_path)
        fast = next(item for item in body["models"] if item["role"] == "fast")
        assert fast["extra"] == "llm"
        assert fast["install_command"] == "uv sync --extra llm"
        assert fast["overridden"] is False
        assert fast["spec"]["repo_id"] == fast["repo_id"]
        assert set(fast["spec"]) == {
            "repo_id",
            "revision",
            "filename",
            "files",
            "device",
            "gpu_layers",
            "context_size",
            "max_tokens",
            "voice",
            "speed",
            "steps",
        }
        assert fast["setup"] == {
            "download": {
                "state": "idle",
                "started_at": None,
                "ended_at": None,
                "error": None,
                "log": [],
            },
            "install": {
                "state": "idle",
                "started_at": None,
                "ended_at": None,
                "error": None,
                "log": [],
            },
        }


def test_download_endpoint_runs_hub_in_background(tmp_path, monkeypatch):
    settings, _, app = _local_client(tmp_path, monkeypatch)
    release = threading.Event()

    def blocking_download(spec):
        release.wait(5)
        return {"revision": "d" * 40}

    with (
        TestClient(app) as client,
        patch.object(app.state.hub, "download", side_effect=blocking_download) as dl,
    ):
        assert client.post("/api/models/nope/download").status_code == 404
        assert client.post("/api/models/images/download").status_code == 409
        started = client.post("/api/models/fast/download")
        assert started.status_code == 202
        assert started.json()["setup"]["state"] == "running"
        assert client.get("/api/models").json()["setup_running"] is True
        busy = client.post("/api/models/fast/download")
        assert busy.status_code == 409
        assert "already running" in busy.json()["detail"]
        blocked = client.post("/api/models/fast/config", json={"gpu_layers": 2})
        assert blocked.status_code == 409
        release.set()
        entry = _poll_setup(client, "fast", "download")
        assert entry["setup"]["download"]["state"] == "done"
        assert dl.call_args.args[0] == settings.models.models["fast"]
        assert client.get("/api/models").json()["setup_running"] is False


def test_install_endpoint_uses_fixed_command(tmp_path, monkeypatch):
    _, _, app = _local_client(tmp_path, monkeypatch)
    calls = []

    def factory(extra):
        calls.append(extra)
        return [sys.executable, "-c", "print('installed')"]

    app.state.setup.command_factory = factory
    with TestClient(app) as client:
        started = client.post("/api/models/fast/install-runtime")
        assert started.status_code == 202
        assert started.json()["extra"] == "llm"
        entry = _poll_setup(client, "fast", "install")
        assert entry["setup"]["install"]["state"] == "done"
        assert "installed" in entry["setup"]["install"]["log"]
        assert calls == ["llm"]
        # Quality shares the llm extra, so its card reflects the same install.
        quality = next(
            item
            for item in client.get("/api/models").json()["models"]
            if item["role"] == "quality"
        )
        assert quality["setup"]["install"]["state"] == "done"


def test_config_override_endpoints(tmp_path, monkeypatch):
    settings, provider, app = _local_client(tmp_path, monkeypatch)
    with TestClient(app) as client:
        before = provider.config_hash
        saved = client.post("/api/models/fast/config", json={"gpu_layers": 4})
        assert saved.status_code == 200
        fast = next(item for item in saved.json()["models"] if item["role"] == "fast")
        assert fast["overridden"] is True
        assert fast["spec"]["gpu_layers"] == 4
        assert settings.model_overlay_path.exists()
        assert provider.config_hash != before
        assert client.post("/api/models/fast/config", json={}).status_code == 422
        assert (
            client.post(
                "/api/models/fast/config", json={"runtime": "kokoro"}
            ).status_code
            == 422
        )
        rejected = client.post("/api/models/embeddings/config", json={"device": "cuda"})
        assert rejected.status_code == 422
        assert "CPU" in rejected.json()["detail"]
        assert settings.models.models["embeddings"].device == "cpu"
        assert client.post("/api/models/nope/config/reset").status_code == 404
        reset = client.post("/api/models/fast/config/reset")
        assert reset.status_code == 200
        fast = next(item for item in reset.json()["models"] if item["role"] == "fast")
        assert fast["overridden"] is False
        assert not settings.model_overlay_path.exists()
        assert provider.config_hash == before


def test_config_change_is_recorded_and_job_continues(tmp_path, monkeypatch):
    settings, provider, app = _local_client(tmp_path, monkeypatch)
    settings.run_worker = False
    with TestClient(app) as client:
        job = client.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "sources": [
                    {
                        "id": "s1",
                        "url": "https://example.com",
                        "title": "DNS reference",
                        "excerpt": "DNS maps domain names to IP addresses.",
                    }
                ],
            },
        ).json()
        assert job["config_hash"] == provider.config_hash
        assert job["stage_hashes"] == provider.stage_hashes
        before = provider.stage_hashes
        client.post("/api/models/fast/config", json={"context_size": 4096})
        assert job["config_hash"] != provider.config_hash
        # Only stages routed to the changed role carry a new fingerprint.
        changed = {s for s in before if before[s] != provider.stage_hashes[s]}
        assert changed == {"research", "metadata"}
        # The run is not blocked; the change is recorded on the job instead.
        assert client.post(f"/api/jobs/{job['id']}/run").status_code == 200
        queued = client.get(f"/api/jobs/{job['id']}").json()
        assert queued["status"] == "queued"
        assert queued["config_hash"] == provider.config_hash
        (change,) = queued["config_changes"]
        assert change["previous"] == job["config_hash"]
        assert change["current"] == provider.config_hash
        assert change["pending_stages_affected"] == ["research", "metadata"]
        # Legacy jobs without stage fingerprints report every pending stage.
        legacy = client.post(
            "/api/jobs",
            json={"title": "Legacy", "sources": job["sources"]},
        ).json()
        stored = provider.store.get(legacy["id"])
        stored["config_hash"], stored["stage_hashes"] = "old", None
        provider.store.save(stored)
        assert client.post(f"/api/jobs/{legacy['id']}/run").status_code == 200
        (change,) = client.get(f"/api/jobs/{legacy['id']}").json()["config_changes"]
        assert change["pending_stages_affected"] == STAGES


def test_local_render_success_reaches_approval_and_serves_video(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    path = str(tmp_path / "jobs.db")
    provider = LocalProvider(settings, Store(path), PipelineFixtureRunner())

    async def fake_render(job, artifacts, library):
        media = artifacts.folder(job["id"]) / "fixture.mp4"
        media.write_bytes(b"offline renderer fixture")
        return {"video": artifacts.adopt(job["id"], media)}

    provider.renderer.render = fake_render
    with TestClient(create_app(path, provider, settings)) as client:
        job = client.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "sources": [
                    {
                        "id": "s1",
                        "url": "https://example.com",
                        "title": "DNS reference",
                        "excerpt": "DNS maps domain names to IP addresses.",
                    }
                ],
            },
        ).json()
        client.post(f"/api/jobs/{job['id']}/run")
        ready = wait(client, job["id"], "awaiting_approval")
        render = next(
            stage["output"] for stage in ready["stages"] if stage["name"] == "render"
        )
        assert (
            client.get(
                f"/api/jobs/{job['id']}/artifacts/{render['video']['id']}"
            ).content
            == b"offline renderer fixture"
        )
        assert ready["approved_at"] is None
        assert ready["stages"][-1]["status"] == "pending"
        assert client.post(f"/api/jobs/{job['id']}/approve").status_code == 200
        failed = wait(client, job["id"], "failed")
        assert "YouTube upload is not connected" in failed["error"]


def test_manual_script_stage_parks_and_resumes_via_api(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    settings.models.routes["script"] = "manual"
    path = str(tmp_path / "jobs.db")
    store = Store(path)
    provider = LocalProvider(settings, store, PipelineFixtureRunner())
    with TestClient(create_app(path, provider, settings)) as client:
        response = client.post(
            "/api/jobs",
            json={
                "title": "DNS",
                "sources": [
                    {
                        "id": "s1",
                        "url": "https://example.com",
                        "title": "DNS reference",
                        "excerpt": "DNS maps domain names to IP addresses.",
                    }
                ],
            },
        )
        job_id = response.json()["id"]
        assert client.post(f"/api/jobs/{job_id}/run").status_code == 200

        job = wait(client, job_id, "awaiting_manual_input")
        script_stage = next(s for s in job["stages"] if s["name"] == "script")
        assert script_stage["status"] == "awaiting_input"
        prompt = script_stage["output"]["manual"]["prompt"]
        assert "ScriptSection" in prompt

        # A stage not currently parked refuses the paste-back.
        wrong_stage = client.post(
            f"/api/jobs/{job_id}/stages/outline/manual-response",
            json={"response": "[]"},
        )
        assert wrong_stage.status_code == 409

        # Malformed JSON is rejected before touching any state; job stays parked.
        bad = client.post(
            f"/api/jobs/{job_id}/stages/script/manual-response",
            json={"response": "not json"},
        )
        assert bad.status_code == 400
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "awaiting_manual_input"

        good = client.post(
            f"/api/jobs/{job_id}/stages/script/manual-response",
            json={
                "response": json.dumps(
                    [
                        {
                            "text": "This is a long enough narration for one section.",
                            "claim_ids": ["c1"],
                        }
                    ]
                )
            },
        )
        assert good.status_code == 200

        job = wait(client, job_id, "awaiting_approval")
        script_stage = next(s for s in job["stages"] if s["name"] == "script")
        assert script_stage["status"] == "completed"
        assert script_stage["output"]["text"] == "This is a long enough narration for one section."

        # No longer parked: resubmitting now 409s instead of silently reapplying.
        again = client.post(
            f"/api/jobs/{job_id}/stages/script/manual-response",
            json={"response": "[]"},
        )
        assert again.status_code == 409
