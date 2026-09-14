"""Series persistence: bibles (append-only), themes, idea backlog, job snapshots."""

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import Series, SeriesBibleVersion, SeriesIdea, SeriesTheme
from .schema import SeriesBible, ThemeGuidance, merge


class SeriesNotFound(KeyError):
    pass


class SeriesConflict(ValueError):
    pass


def now():
    return datetime.now(UTC)


def digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "series"


def _row(row, keys):
    data = {}
    for key in keys:
        value = getattr(row, key)
        if isinstance(value, datetime):
            # SQLite drops tzinfo; stored values are always UTC.
            value = (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
        data[key] = value
    return data


SERIES_KEYS = ("id", "slug", "name", "description", "created_at", "updated_at")
THEME_KEYS = (
    "id",
    "series_id",
    "name",
    "blurb",
    "guidance",
    "created_at",
    "updated_at",
)
IDEA_KEYS = (
    "id",
    "series_id",
    "theme_id",
    "title",
    "pitch",
    "notes",
    "status",
    "job_id",
    "created_at",
    "updated_at",
)


class SeriesStore:
    def __init__(self, engine):
        self.engine = engine

    # Series -----------------------------------------------------------------

    def list(self):
        with Session(self.engine) as session:
            rows = session.scalars(select(Series).order_by(Series.created_at.desc()))
            return [_row(row, SERIES_KEYS) for row in rows]

    def get(self, series_id):
        with Session(self.engine) as session:
            return _row(self._series(session, series_id), SERIES_KEYS)

    def create(self, name, description="", slug=None):
        stamp, series_id = now(), str(uuid4())
        row = Series(
            id=series_id,
            slug=slug or slugify(name),
            name=name,
            description=description,
            created_at=stamp,
            updated_at=stamp,
        )
        try:
            with Session(self.engine) as session, session.begin():
                session.add(row)
        except IntegrityError as exc:
            raise SeriesConflict(
                f"Series slug '{slug or slugify(name)}' already exists"
            ) from exc
        return self.get(series_id)

    def update(self, series_id, **fields):
        try:
            with Session(self.engine) as session, session.begin():
                row = self._series(session, series_id)
                for key, value in fields.items():
                    setattr(row, key, value)
                row.updated_at = now()
        except IntegrityError as exc:
            raise SeriesConflict("Series slug already exists") from exc
        return self.get(series_id)

    def delete(self, series_id):
        with Session(self.engine) as session, session.begin():
            row = self._series(session, series_id)
            for model in (SeriesIdea, SeriesTheme, SeriesBibleVersion):
                for child in session.scalars(
                    select(model).where(model.series_id == series_id)
                ):
                    session.delete(child)
            session.flush()
            session.delete(row)

    # Bible ------------------------------------------------------------------

    def bible(self, series_id):
        with Session(self.engine) as session:
            self._series(session, series_id)
            row = session.scalars(
                select(SeriesBibleVersion)
                .where(SeriesBibleVersion.series_id == series_id)
                .order_by(SeriesBibleVersion.version.desc())
                .limit(1)
            ).first()
            if row is None:
                document = SeriesBible().model_dump()
                return {
                    "version": 0,
                    "document": document,
                    "sha256": digest(document),
                    "created_at": None,
                }
            return _row(row, ("version", "document", "sha256", "created_at"))

    def bible_versions(self, series_id):
        with Session(self.engine) as session:
            self._series(session, series_id)
            rows = session.scalars(
                select(SeriesBibleVersion)
                .where(SeriesBibleVersion.series_id == series_id)
                .order_by(SeriesBibleVersion.version.desc())
            )
            return [_row(row, ("version", "sha256", "created_at")) for row in rows]

    def put_bible(self, series_id, document: SeriesBible):
        data = document.model_dump()
        try:
            with Session(self.engine) as session, session.begin():
                row = self._series(session, series_id)
                latest = session.scalar(
                    select(func.max(SeriesBibleVersion.version)).where(
                        SeriesBibleVersion.series_id == series_id
                    )
                )
                session.add(
                    SeriesBibleVersion(
                        id=str(uuid4()),
                        series_id=series_id,
                        version=(latest or 0) + 1,
                        document=data,
                        sha256=digest(data),
                        created_at=now(),
                    )
                )
                row.updated_at = now()
        except IntegrityError as exc:
            # Concurrent writers raced for the same version number.
            raise SeriesConflict("Bible was updated concurrently; retry") from exc
        return self.bible(series_id)

    # Themes -----------------------------------------------------------------

    def themes(self, series_id):
        with Session(self.engine) as session:
            self._series(session, series_id)
            rows = session.scalars(
                select(SeriesTheme)
                .where(SeriesTheme.series_id == series_id)
                .order_by(SeriesTheme.created_at)
            )
            return [_row(row, THEME_KEYS) for row in rows]

    def theme(self, series_id, theme_id):
        with Session(self.engine) as session:
            return _row(self._theme(session, series_id, theme_id), THEME_KEYS)

    def create_theme(
        self, series_id, name, blurb="", guidance: ThemeGuidance | None = None
    ):
        stamp, theme_id = now(), str(uuid4())
        row = SeriesTheme(
            id=theme_id,
            series_id=series_id,
            name=name,
            blurb=blurb,
            guidance=(guidance or ThemeGuidance()).model_dump(),
            created_at=stamp,
            updated_at=stamp,
        )
        with Session(self.engine) as session, session.begin():
            self._series(session, series_id)
            session.add(row)
        return self.theme(series_id, theme_id)

    def update_theme(self, series_id, theme_id, **fields):
        with Session(self.engine) as session, session.begin():
            row = self._theme(session, series_id, theme_id)
            for key, value in fields.items():
                if key == "guidance":
                    value = value.model_dump()
                setattr(row, key, value)
            row.updated_at = now()
        return self.theme(series_id, theme_id)

    def delete_theme(self, series_id, theme_id):
        with Session(self.engine) as session, session.begin():
            row = self._theme(session, series_id, theme_id)
            for idea in session.scalars(
                select(SeriesIdea).where(SeriesIdea.theme_id == theme_id)
            ):
                idea.theme_id = None
            session.flush()
            session.delete(row)

    # Ideas ------------------------------------------------------------------

    def ideas(self, series_id):
        with Session(self.engine) as session:
            self._series(session, series_id)
            rows = session.scalars(
                select(SeriesIdea)
                .where(SeriesIdea.series_id == series_id)
                .order_by(SeriesIdea.created_at.desc())
            )
            return [_row(row, IDEA_KEYS) for row in rows]

    def idea(self, series_id, idea_id):
        with Session(self.engine) as session:
            return _row(self._idea(session, series_id, idea_id), IDEA_KEYS)

    def create_idea(self, series_id, title, pitch="", notes="", theme_id=None):
        stamp, idea_id = now(), str(uuid4())
        row = SeriesIdea(
            id=idea_id,
            series_id=series_id,
            theme_id=theme_id,
            title=title,
            pitch=pitch,
            notes=notes,
            status="backlog",
            job_id=None,
            created_at=stamp,
            updated_at=stamp,
        )
        with Session(self.engine) as session, session.begin():
            self._series(session, series_id)
            if theme_id:
                self._theme(session, series_id, theme_id)
            session.add(row)
        return self.idea(series_id, idea_id)

    def update_idea(self, series_id, idea_id, **fields):
        with Session(self.engine) as session, session.begin():
            row = self._idea(session, series_id, idea_id)
            if fields.get("theme_id"):
                self._theme(session, series_id, fields["theme_id"])
            if "status" in fields and row.job_id:
                raise SeriesConflict(
                    "This idea already has a video; delete the video to change its status"
                )
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = now()
        return self.idea(series_id, idea_id)

    def delete_idea(self, series_id, idea_id):
        with Session(self.engine) as session, session.begin():
            session.delete(self._idea(session, series_id, idea_id))

    def link_job(self, series_id, idea_id, job_id):
        """Claim a backlog idea for a job; one winner under concurrent starts."""
        with Session(self.engine) as session, session.begin():
            row = self._idea(session, series_id, idea_id)
            if row.job_id or row.status != "backlog":
                raise SeriesConflict(
                    "Only backlog ideas without a video can be started"
                )
            row.job_id, row.status, row.updated_at = job_id, "started", now()
        return self.idea(series_id, idea_id)

    def release_job(self, job_id):
        """Return ideas linked to a deleted job to the backlog."""
        with Session(self.engine) as session, session.begin():
            for row in session.scalars(
                select(SeriesIdea).where(SeriesIdea.job_id == job_id)
            ):
                row.job_id, row.status, row.updated_at = None, "backlog", now()

    # Job snapshots ------------------------------------------------------------

    def resolve_context(self, series_id, theme_id=None):
        """Merged bible + theme overlay that a job snapshots at creation."""
        series = self.get(series_id)
        bible = self.bible(series_id)
        guidance = bible["document"]
        theme = None
        if theme_id:
            row = self.theme(series_id, theme_id)
            theme = {"id": row["id"], "name": row["name"], "blurb": row["blurb"]}
            guidance = merge(guidance, row["guidance"])
        content = {"guidance": guidance, "theme": theme}
        return {
            "series": {"id": series["id"], "name": series["name"]},
            "bible_version": bible["version"],
            **content,
            "hash": digest(content),
        }

    def current_hash(self, series_id, theme_id=None):
        """None when the series or theme no longer exists."""
        try:
            return self.resolve_context(series_id, theme_id)["hash"]
        except SeriesNotFound:
            return None

    # Lookups ------------------------------------------------------------------

    def _series(self, session, series_id):
        row = session.get(Series, series_id)
        if row is None:
            raise SeriesNotFound("Series not found")
        return row

    def _theme(self, session, series_id, theme_id):
        row = session.get(SeriesTheme, theme_id)
        if row is None or row.series_id != series_id:
            raise SeriesNotFound("Theme not found in this series")
        return row

    def _idea(self, session, series_id, idea_id):
        row = session.get(SeriesIdea, idea_id)
        if row is None or row.series_id != series_id:
            raise SeriesNotFound("Idea not found in this series")
        return row
