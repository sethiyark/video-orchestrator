import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from app.store import Store, now


def test_legacy_import_is_idempotent_and_preserves_pipeline(tmp_path):
    path = str(tmp_path / "legacy.db")
    job = {
        "id": str(uuid4()),
        "title": "Legacy",
        "brief": "",
        "status": "awaiting_approval",
        "created_at": now(),
        "updated_at": now(),
        "approved_at": None,
        "error": None,
        "stages": [{"name": "upload", "status": "pending", "output": None}],
    }
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, data TEXT)")
        db.execute("INSERT INTO jobs VALUES (?, ?)", (job["id"], json.dumps(job)))
    store = Store(path)
    assert store.get(job["id"])["stages"] == job["stages"]
    assert len(Store(path).list()) == 1
    names = set(inspect(store.engine).get_table_names())
    assert {
        "video_jobs",
        "video_stages",
        "stage_attempts",
        "alembic_version",
        "jobs",
        "channels",
        "video_projects",
        "workflow_runs",
        "assets",
        "model_runs",
        "gpu_jobs",
    } <= names


def test_concurrent_transitions_have_one_winner(tmp_path):
    store = Store(str(tmp_path / "jobs.db"))
    job = store.create("Concurrent", "")
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda _: store.transition(job["id"], ["draft"], "queued"), range(2)
            )
        )
    assert sum(result is not None for result in results) == 1
    assert store.claim()["id"] == job["id"]
    assert store.claim() is None
    store.engine.dispose()


def test_worker_lock_excludes_second_worker(tmp_path):
    from filelock import Timeout

    store = Store(str(tmp_path / "jobs.db"))
    with store.worker_lock(), pytest.raises(Timeout), store.worker_lock():
        pass


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a disposable PostgreSQL database",
)
def test_postgres_state_and_advisory_lock():
    store = Store(os.environ["TEST_DATABASE_URL"])
    assert store.engine.dialect.name == "postgresql"
    job = store.create("Postgres integration " + str(uuid4()), "")
    assert store.get(job["id"])["title"] == job["title"]
    assert store.transition(job["id"], ["draft"], "queued")
    assert store.transition(job["id"], ["draft"], "queued") is None
    attempt = store.start_attempt(job["id"], "research")
    store.finish_attempt(attempt, "completed", provenance={"revision": "test"})
    assert store.attempts(job["id"])[0]["provenance"] == {"revision": "test"}
    with (
        store.worker_lock(),
        pytest.raises(RuntimeError, match="already owns"),
        store.worker_lock(),
    ):
        pass
    store.engine.dispose()
