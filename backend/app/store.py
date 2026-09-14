import json
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from filelock import FileLock
from sqlalchemy import delete as sa_delete
from sqlalchemy import inspect, select, text, update
from sqlalchemy.orm import Session

from .db import Attempt, StageRecord, VideoJob, make_engine, migrate
from .providers import STAGES

RESTARTABLE = (
    "draft",
    "failed",
    "awaiting_approval",
    "awaiting_manual_input",
    "completed",
)


def now():
    return datetime.now(UTC).isoformat()


def series_fields(context):
    """Job context keys for a series snapshot (all None for standalone jobs)."""
    return {
        "series_id": context["series"]["id"] if context else None,
        "theme_id": (context["theme"] or {}).get("id") if context else None,
        "series_context": context,
        "series_hash": context["hash"] if context else None,
    }


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

    def create(
        self,
        title,
        brief,
        sources=None,
        mode="mock",
        config_hash=None,
        series_context=None,
        idea_id=None,
        stage_hashes=None,
    ):
        return self.save(
            {
                **series_fields(series_context),
                "idea_id": idea_id,
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
                "stage_hashes": stage_hashes,
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

    def restart(self, job_id, config_hash=None, series_context=None, stage_hashes=None):
        """Wipe stage outputs, rebind config_hash (and series snapshot), and queue."""
        with Session(self.engine) as session, session.begin():
            row = session.get(VideoJob, job_id)
            if row is None or row.status not in RESTARTABLE:
                return None
            row.status = "queued"
            row.error = None
            row.approved_at = None
            row.updated_at = now()
            row.context = {
                **(row.context or {}),
                "config_hash": config_hash,
                "stage_hashes": stage_hashes,
                "config_changes": [],
                "rewinds": {},
                "corrections": {},
                **(series_fields(series_context) if series_context else {}),
            }
            stages = session.scalars(
                select(StageRecord).where(StageRecord.job_id == job_id)
            ).all()
            for stage in stages:
                stage.status = "pending"
                stage.output = None
        return self.get(job_id)

    def submit_manual_response(self, job_id, stage_name, raw_text):
        """Record a pasted response for a stage parked on manual input, and
        re-queue the job so the worker resumes it. Returns None (caller should
        treat as a 409) if the job/stage isn't actually parked."""
        with Session(self.engine) as session, session.begin():
            job_row = session.get(VideoJob, job_id)
            if job_row is None or job_row.status != "awaiting_manual_input":
                return None
            stage_row = session.get(StageRecord, (job_id, stage_name))
            if stage_row is None or stage_row.status != "awaiting_input":
                return None
            manual = dict((stage_row.output or {}).get("manual") or {})
            responses = dict(manual.get("responses") or {})
            responses[str(len(responses))] = raw_text
            stage_row.output = {**(stage_row.output or {}), "manual": {**manual, "responses": responses}}
            stage_row.status = "pending"
            job_row.status = "queued"
            job_row.error = None
            job_row.updated_at = now()
        return self.get(job_id)

    def delete(self, job_id):
        """Remove a job and its attempts/stages. Returns False if it never existed."""
        with Session(self.engine) as session, session.begin():
            row = session.get(VideoJob, job_id)
            if row is None:
                return False
            session.execute(sa_delete(Attempt).where(Attempt.job_id == job_id))
            session.execute(sa_delete(StageRecord).where(StageRecord.job_id == job_id))
            session.delete(row)
        return True

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
