import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.local_provider import ReviewRequired
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


def test_delete_job_removes_job_and_attempts(tmp_path):
    provider = MockProvider(0)
    with TestClient(create_app(str(tmp_path / "jobs.db"), provider)) as client:
        job_id = client.post("/api/jobs", json={"title": "Delete me"}).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        wait(client, job_id, "awaiting_approval")
        assert client.get(f"/api/jobs/{job_id}/attempts").json()

        assert client.delete(f"/api/jobs/{job_id}").status_code == 204
        assert client.get(f"/api/jobs/{job_id}").status_code == 404
        assert client.get(f"/api/jobs/{job_id}/attempts").status_code == 404
        assert job_id not in [job["id"] for job in client.get("/api/jobs").json()]


def test_delete_unknown_job_is_404(tmp_path):
    with TestClient(create_app(str(tmp_path / "jobs.db"), MockProvider(0))) as client:
        assert client.delete("/api/jobs/missing").status_code == 404


def test_retry_resumes_completed_stages(tmp_path):
    class FlakyProvider(MockProvider):
        failed = False

        def __init__(self, delay):
            super().__init__(delay)
            self.calls = []

        async def execute(self, stage, job, attempt=0):
            self.calls.append(stage)
            if stage == "script" and not self.failed:
                self.failed = True
                raise RuntimeError("Temporary provider error")
            return await super().execute(stage, job, attempt)

    provider = FlakyProvider(0)
    with TestClient(create_app(str(tmp_path / "jobs.db"), provider)) as client:
        job_id = client.post("/api/jobs", json={"title": "Retry example"}).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        assert wait(client, job_id, "failed")["error"] == "Temporary provider error"
        client.post(f"/api/jobs/{job_id}/run")
        wait(client, job_id, "awaiting_approval")
        assert provider.calls.count("research") == 1
        assert provider.calls.count("script") == 2


def test_restart_replays_completed_stages(tmp_path):
    provider = MockProvider(0)
    with TestClient(create_app(str(tmp_path / "jobs.db"), provider)) as client:
        job_id = client.post("/api/jobs", json={"title": "Restart example"}).json()[
            "id"
        ]
        client.post(f"/api/jobs/{job_id}/run")
        wait(client, job_id, "awaiting_approval")
        assert client.post(f"/api/jobs/{job_id}/run").status_code == 409
        restarted = client.post(f"/api/jobs/{job_id}/restart").json()
        assert restarted["status"] == "queued"
        assert all(stage["status"] == "pending" for stage in restarted["stages"])
        wait(client, job_id, "awaiting_approval")


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

        async def execute(self, stage, job, attempt=0):
            self.calls.append(job["id"])
            return await super().execute(stage, job, attempt)

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


class RewindingProvider(MockProvider):
    """Mock stages, except critique rejects the script ``failures`` times and
    asks the worker to go back to script with corrections."""

    def __init__(self, failures):
        super().__init__(0)
        self.failures = failures
        self.calls = []
        self.corrections_seen = []

    async def execute(self, stage, job, attempt=0):
        self.calls.append(stage)
        if stage == "script":
            self.corrections_seen.append((job.get("corrections") or {}).get("script"))
        if stage == "critique" and self.calls.count("critique") <= self.failures:
            raise ReviewRequired(
                "Script did not pass independent critics",
                {"required_changes": {"clarity": ["Cut the repetition."]}},
                rewind_to="script",
            )
        return await super().execute(stage, job, attempt)


def local_settings(tmp_path, max_rewinds):
    settings = Settings()
    settings.mode = "local"
    settings.artifact_dir = tmp_path / "artifacts"
    settings.cache_dir = tmp_path / "models"
    settings.models.governor.max_rewinds = max_rewinds
    return settings


SOURCES = [
    {
        "id": "s1",
        "url": "https://example.com",
        "title": "Reference",
        "excerpt": "DNS maps domain names to IP addresses.",
    }
]


def test_failed_stage_rewinds_with_corrections_and_continues(tmp_path):
    provider = RewindingProvider(failures=1)
    settings = local_settings(tmp_path, max_rewinds=2)
    with TestClient(
        create_app(str(tmp_path / "jobs.db"), provider, settings)
    ) as client:
        job_id = client.post(
            "/api/jobs", json={"title": "DNS", "sources": SOURCES}
        ).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        job = wait(client, job_id, "awaiting_approval")
    # Script ran again with the critics' corrections, then critique passed.
    assert provider.calls.count("research") == 1
    assert provider.calls.count("script") == 2
    assert provider.calls.count("critique") == 2
    assert provider.corrections_seen[0] is None
    assert provider.corrections_seen[1]["from_stage"] == "critique"
    assert provider.corrections_seen[1]["required_changes"] == {
        "clarity": ["Cut the repetition."]
    }
    assert job["rewinds"] == {"critique": 1}
    # Consumed once critique passed.
    assert job["corrections"] == {}
    attempts = client.get(f"/api/jobs/{job_id}/attempts").json()
    assert [a["status"] for a in attempts if a["stage"] == "critique"] == [
        "failed",
        "completed",
    ]


def test_rewind_budget_is_bounded_then_requires_review(tmp_path):
    provider = RewindingProvider(failures=10)
    settings = local_settings(tmp_path, max_rewinds=2)
    with TestClient(
        create_app(str(tmp_path / "jobs.db"), provider, settings)
    ) as client:
        job_id = client.post(
            "/api/jobs", json={"title": "DNS", "sources": SOURCES}
        ).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        job = wait(client, job_id, "failed")
        assert "independent critics" in job["error"]
        assert job["rewinds"] == {"critique": 2}
        assert provider.calls.count("script") == 3
        assert provider.calls.count("critique") == 3
        # Restart clears the loop state along with the stage outputs.
        restarted = client.post(f"/api/jobs/{job_id}/restart").json()
        assert restarted["rewinds"] == {} and restarted["corrections"] == {}


def test_mock_mode_never_rewinds(tmp_path):
    provider = RewindingProvider(failures=1)
    with TestClient(create_app(str(tmp_path / "jobs.db"), provider)) as client:
        job_id = client.post("/api/jobs", json={"title": "DNS"}).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        job = wait(client, job_id, "failed")
    assert provider.calls.count("script") == 1
    assert "rewinds" not in job


def test_local_retries_pass_increasing_attempt_index_to_the_provider(tmp_path):
    """A deterministic local model reproduces the same bad output on an unvaried
    retry, so the worker's bounded retry loop (main.py) must tell the provider
    which attempt it's on rather than replaying an identical request."""

    class FlakyLocalProvider(MockProvider):
        def __init__(self):
            super().__init__(0)
            self.script_attempts = []

        async def execute(self, stage, job, attempt=0):
            if stage == "script":
                self.script_attempts.append(attempt)
                if attempt < 2:
                    raise RuntimeError("Deterministic model failure")
            return await super().execute(stage, job, attempt)

    provider = FlakyLocalProvider()
    settings = local_settings(tmp_path, max_rewinds=0)
    settings.models.governor.max_attempts = 3
    with TestClient(
        create_app(str(tmp_path / "jobs.db"), provider, settings)
    ) as client:
        job_id = client.post(
            "/api/jobs", json={"title": "DNS", "sources": SOURCES}
        ).json()["id"]
        client.post(f"/api/jobs/{job_id}/run")
        wait(client, job_id, "awaiting_approval")
    assert provider.script_attempts == [0, 1, 2]


def test_config_change_mid_run_is_recorded_not_blocking(tmp_path):
    provider = RewindingProvider(failures=0)
    provider.config_hash = "v1"
    provider.stage_hashes = {"research": "r1", "script": "s1"}
    settings = local_settings(tmp_path, max_rewinds=0)
    with TestClient(
        create_app(str(tmp_path / "jobs.db"), provider, settings)
    ) as client:
        job_id = client.post(
            "/api/jobs", json={"title": "DNS", "sources": SOURCES}
        ).json()["id"]
        # Operator changes the script model before the job runs.
        provider.config_hash = "v2"
        provider.stage_hashes = {"research": "r1", "script": "s2"}
        assert client.post(f"/api/jobs/{job_id}/run").status_code == 200
        job = wait(client, job_id, "awaiting_approval")
    assert job["config_hash"] == "v2"
    (change,) = job["config_changes"]
    assert (change["previous"], change["current"]) == ("v1", "v2")
    assert change["pending_stages_affected"] == ["script"]
    assert provider.calls.count("script") == 1
