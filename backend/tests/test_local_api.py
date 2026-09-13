from pathlib import Path

from fastapi.testclient import TestClient
from test_pipeline import wait

from app.config import Settings
from app.local_provider import LocalProvider
from app.main import create_app
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
            return {"duration_seconds": 1, "provenance": provenance}
        if role == "alignment":
            assert Path(payload["audio_path"]).exists()
            return {
                "segments": [{"text": "DNS maps names", "start": 0, "end": 1}],
                "provenance": provenance,
            }
        if role == "embeddings":
            return {"embeddings": [[1.0, 0.0]], "provenance": provenance}
        schema = payload["schema"]["title"]
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
            "Script": {
                "text": "DNS maps domain names to IP addresses.",
                "claim_ids": ["c1"],
            },
            "Critic": {
                "score": 9.5,
                "issues": [],
                "required_changes": [],
                "optional_changes": [],
            },
            "Storyboard": {
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "component": "DefinitionCard",
                        "props": {"title": "DNS", "body": "Domain name system"},
                        "narration_text": "DNS maps domain names to IP addresses.",
                        "duration_seconds": 10,
                    }
                ]
            },
            "Metadata": {
                "title": "DNS explained",
                "description": "DNS basics",
                "tags": ["DNS"],
            },
        }
        return {"result": results[schema], "provenance": provenance}


def test_local_pipeline_artifacts_and_explicit_render_boundary(tmp_path):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    path = str(tmp_path / "jobs.db")
    provider = LocalProvider(settings, Store(path), PipelineFixtureRunner())
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
