import json
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from filelock import FileLock
from sqlalchemy import inspect, select, text, update
from sqlalchemy.orm import Session

from .db import Attempt, StageRecord, VideoJob, make_engine, migrate
from .providers import STAGES


def now():
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        migrate(self.engine)
        # Preserve and import legacy SQLite JSON rows without changing their pipeline.
        if "jobs" in inspect(self.engine).get_table_names():
            with self.engine.connect() as db:
                legacy = [
                    json.loads(row[0])
                    for row in db.execute(text("SELECT data FROM jobs"))
                ]
            for job in legacy:
                if self.get(job["id"]) is None:
                    self.save(job)

    @contextmanager
    def worker_lock(self):
        """One model worker per database, including separate uvicorn processes."""
        if self.engine.dialect.name == "postgresql":
            with self.engine.connect() as connection:
                if not connection.scalar(text("SELECT pg_try_advisory_lock(76329011)")):
                    raise RuntimeError(
                        "A worker already owns this database; set RUN_WORKER=false for API replicas"
                    )
                try:
                    yield
                finally:
                    connection.execute(text("SELECT pg_advisory_unlock(76329011)"))
        else:
            with FileLock(str(self.engine.url.database) + ".worker.lock", timeout=0):
                yield

    def _serialize(self, session, row):
        if row is None:
            return None
        stages = session.scalars(
            select(StageRecord)
            .where(StageRecord.job_id == row.id)
            .order_by(StageRecord.position)
        ).all()
        return {
            **row.context,
            **{
                key: getattr(row, key)
                for key in (
                    "id",
                    "title",
                    "brief",
                    "status",
                    "created_at",
                    "updated_at",
                    "approved_at",
                    "error",
                )
            },
            "stages": [
                {"name": stage.name, "status": stage.status, "output": stage.output}
                for stage in stages
            ],
        }

    def list(self):
        with Session(self.engine) as session:
            return [
                self._serialize(session, row)
                for row in session.scalars(
                    select(VideoJob).order_by(VideoJob.created_at.desc())
                )
            ]

    def get(self, job_id):
        with Session(self.engine) as session:
            return self._serialize(session, session.get(VideoJob, job_id))

    def save(self, job):
        job["updated_at"] = now()
        with Session(self.engine) as session, session.begin():
            row = session.get(VideoJob, job["id"])
            if row is None:
                row = VideoJob(id=job["id"])
                session.add(row)
            keys = (
                "title",
                "brief",
                "status",
                "created_at",
                "updated_at",
                "approved_at",
                "error",
            )
            for key in keys:
                setattr(row, key, job[key])
            row.context = {
                key: value
                for key, value in job.items()
                if key not in (*keys, "id", "stages")
            }
            session.flush()
            for position, stage in enumerate(job["stages"]):
                session.merge(StageRecord(job_id=job["id"], position=position, **stage))
        return job

    def create(self, title, brief, sources=None, mode="mock", config_hash=None):
        return self.save(
            {
                "id": str(uuid4()),
                "title": title,
                "brief": brief,
                "status": "draft",
                "created_at": now(),
                "approved_at": None,
                "error": None,
                "sources": sources or [],
                "mode": mode,
                "config_hash": config_hash,
                "stages": [
                    {"name": name, "status": "pending", "output": None}
                    for name in STAGES
                ],
            }
        )

    def transition(self, job_id, allowed, target, approve=False):
        values = {"status": target, "error": None, "updated_at": now()}
        if approve:
            values["approved_at"] = now()
        with Session(self.engine) as session, session.begin():
            result = session.execute(
                update(VideoJob)
                .where(VideoJob.id == job_id, VideoJob.status.in_(allowed))
                .values(**values)
            )
            if result.rowcount != 1:
                return None
        return self.get(job_id)

    def claim(self):
        with Session(self.engine) as session:
            job_id = session.scalar(
                select(VideoJob.id)
                .where(VideoJob.status == "queued")
                .order_by(VideoJob.created_at)
                .limit(1)
            )
        return self.transition(job_id, ["queued"], "running") if job_id else None

    def start_attempt(self, job_id, stage):
        attempt_id = str(uuid4())
        with Session(self.engine) as session, session.begin():
            session.add(
                Attempt(
                    id=attempt_id,
                    job_id=job_id,
                    stage=stage,
                    started_at=now(),
                    status="running",
                    provenance={},
                )
            )
        return attempt_id

    def finish_attempt(self, attempt_id, status, error=None, provenance=None):
        with Session(self.engine) as session, session.begin():
            session.execute(
                update(Attempt)
                .where(Attempt.id == attempt_id)
                .values(
                    status=status,
                    ended_at=now(),
                    error=error,
                    provenance=provenance or {},
                )
            )

    def attempts(self, job_id):
        with Session(self.engine) as session:
            return [
                {
                    key: getattr(row, key)
                    for key in (
                        "id",
                        "stage",
                        "started_at",
                        "ended_at",
                        "status",
                        "error",
                        "provenance",
                    )
                }
                for row in session.scalars(
                    select(Attempt)
                    .where(Attempt.job_id == job_id)
                    .order_by(Attempt.started_at)
                )
            ]

    def recover(self):
        with Session(self.engine) as session, session.begin():
            session.execute(
                update(Attempt)
                .where(Attempt.status == "running")
                .values(
                    status="interrupted", ended_at=now(), error="Worker interrupted"
                )
            )
        for job in self.list():
            if job["status"] == "running":
                job["status"] = "failed"
                job["error"] = (
                    "Worker interrupted. Retry to resume from the last completed stage."
                )
                for stage in job["stages"]:
                    if stage["status"] == "running":
                        stage["status"] = "failed"
                self.save(job)
