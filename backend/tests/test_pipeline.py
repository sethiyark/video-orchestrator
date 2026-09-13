import time

from fastapi.testclient import TestClient

from app.main import create_app
from app.providers import STAGES, MockProvider


def wait(client, job_id, status):
    for _ in range(150):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == status:
            return job
        time.sleep(0.02)
    raise AssertionError(f"Expected {status}, got {job}")


def test_approval_gate_and_persistence(tmp_path):
    path = str(tmp_path / "jobs.db")
    with TestClient(create_app(path, MockProvider(0))) as client:
        assert client.post("/api/jobs", json={"title": "   "}).status_code == 422
        job = client.post(
            "/api/jobs", json={"title": "DNS explained", "brief": "For beginners"}
        ).json()
        job_id = job["id"]
        assert client.post(f"/api/jobs/{job_id}/approve").status_code == 409
        assert client.post(f"/api/jobs/{job_id}/run").status_code == 200
        assert client.post(f"/api/jobs/{job_id}/run").status_code == 409
        ready = wait(client, job_id, "awaiting_approval")
        assert ready["stages"][-1]["status"] == "pending"
        assert all(stage["status"] == "completed" for stage in ready["stages"][:-1])
    with TestClient(create_app(path, MockProvider(0))) as client:
        assert client.get("/api/jobs").json()[0]["status"] == "awaiting_approval"
        assert client.post(f"/api/jobs/{job_id}/approve").status_code == 200
        done = wait(client, job_id, "completed")
        assert done["approved_at"]
        assert done["stages"][-1]["output"]["provider"] == "mock"
        assert client.post(f"/api/jobs/{job_id}/approve").status_code == 409
        assert client.get("/api/jobs/missing").status_code == 404


def test_retry_resumes_completed_stages(tmp_path):
    class FlakyProvider(MockProvider):
        failed = False

        def __init__(self, delay):
            super().__init__(delay)
            self.calls = []

        async def execute(self, stage, job):
            self.calls.append(stage)
            if stage == "script" and not self.failed:
                self.failed = True
                raise RuntimeError("Temporary provider error")
            return await super().execute(stage, job)

    provider = FlakyProvider(0)
    with TestClient(create_app(str(tmp_path / "jobs.db"), provider)) as client:
        job_id = client.post("/api/jobs", json={"title": "Retry example"}).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        assert wait(client, job_id, "failed")["error"] == "Temporary provider error"
        client.post(f"/api/jobs/{job_id}/run")
        wait(client, job_id, "awaiting_approval")
        assert provider.calls.count("research") == 1
        assert provider.calls.count("script") == 2


def test_queue_is_serial_and_interrupted_jobs_are_recoverable(tmp_path):
    from app.store import Store

    path = str(tmp_path / "jobs.db")
    store = Store(path)
    interrupted = store.create("Interrupted video", "")
    interrupted["status"] = "running"
    interrupted["stages"][0]["status"] = "running"
    store.save(interrupted)

    class RecordingProvider(MockProvider):
        def __init__(self, delay):
            super().__init__(delay)
            self.calls = []

        async def execute(self, stage, job):
            self.calls.append(job["id"])
            return await super().execute(stage, job)

    provider = RecordingProvider(0.01)
    with TestClient(create_app(path, provider)) as client:
        recovered = client.get(f"/api/jobs/{interrupted['id']}").json()
        assert recovered["status"] == "failed"
        assert recovered["stages"][0]["status"] == "failed"
        ids = [
            client.post("/api/jobs", json={"title": f"Video {i}"}).json()["id"]
            for i in range(2)
        ]
        for job_id in ids:
            client.post(f"/api/jobs/{job_id}/run")
        for job_id in ids:
            wait(client, job_id, "awaiting_approval")
        assert provider.calls == [ids[0]] * (len(STAGES) - 1) + [ids[1]] * (
            len(STAGES) - 1
        )
