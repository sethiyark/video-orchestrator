"""Series libraries: shared media in the object store and reusable source excerpts."""

import hashlib
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import Asset, Series, SeriesSource
from .store import SeriesConflict, SeriesNotFound, _row, now

# Declared content type → stored suffix. SVG/HTML are excluded: they can script.
MEDIA_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "video/mp4": ".mp4",
}
ASSET_KINDS = ("logo", "image", "audio", "music", "video", "other")
AssetKind = Literal["logo", "image", "audio", "music", "video", "other"]
VISUAL_KINDS = ("logo", "image")
ASSET_KEYS = (
    "id",
    "series_id",
    "name",
    "kind",
    "sha256",
    "byte_size",
    "content_type",
    "status",
    "provenance",
    "created_at",
)
SOURCE_KEYS = ("id", "series_id", "source_key", "url", "title", "excerpt", "created_at")


class UnsupportedMedia(ValueError):
    pass


def _matches(content_type: str, data: bytes) -> bool:
    """Magic-byte check so a renamed HTML file cannot pose as an image."""
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if content_type in ("audio/wav", "audio/x-wav"):
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if content_type == "audio/mpeg":
        return data.startswith(b"ID3") or data[:2] in (
            b"\xff\xfb",
            b"\xff\xf3",
            b"\xff\xf2",
        )
    if content_type == "video/mp4":
        return data[4:8] == b"ftyp"
    return False


class SeriesLibrary:
    """Metadata lives in SQL; bytes go through `ObjectStore` when one is supplied."""

    def __init__(self, engine, objects=None):
        self.engine = engine
        self.objects = objects

    # Media --------------------------------------------------------------------

    async def add(self, series_id, data: bytes, content_type, name, kind, provenance):
        content_type = content_type.split(";")[0].strip().lower()
        if content_type not in MEDIA_TYPES:
            raise UnsupportedMedia(
                f"Unsupported media type {content_type or 'unknown'}; "
                f"allowed: {', '.join(sorted(MEDIA_TYPES))}"
            )
        if not data or not _matches(content_type, data):
            raise UnsupportedMedia(f"File content is not valid {content_type}")
        digest = hashlib.sha256(data).hexdigest()
        key = f"series/{series_id}/{digest}{MEDIA_TYPES[content_type]}"
        existing = self._by_key(key)
        if existing:
            return {**existing, "duplicate": True}
        self._require_series(series_id)
        await self.objects.put(key, data, content_type)
        asset_id = str(uuid4())
        try:
            with Session(self.engine) as session, session.begin():
                session.add(
                    Asset(
                        id=asset_id,
                        project_id=None,
                        series_id=series_id,
                        name=name,
                        kind=kind,
                        object_key=key,
                        sha256=digest,
                        byte_size=len(data),
                        content_type=content_type,
                        status="active",
                        provenance=provenance,
                        created_at=now(),
                    )
                )
        except IntegrityError:
            # A concurrent upload of the same bytes won; both wrote identical content.
            return {**self._by_key(key), "duplicate": True}
        return {**self.asset(series_id, asset_id), "duplicate": False}

    def assets(self, series_id, include_archived=False):
        self._require_series(series_id)
        with Session(self.engine) as session:
            query = select(Asset).where(Asset.series_id == series_id)
            if not include_archived:
                query = query.where(Asset.status == "active")
            rows = session.scalars(query.order_by(Asset.created_at.desc()))
            return [_row(row, ASSET_KEYS) for row in rows]

    def asset(self, series_id, asset_id):
        with Session(self.engine) as session:
            return _row(self._asset(session, series_id, asset_id), ASSET_KEYS)

    def update(self, series_id, asset_id, **fields):
        with Session(self.engine) as session, session.begin():
            row = self._asset(session, series_id, asset_id)
            for key, value in fields.items():
                setattr(row, key, value)
        return self.asset(series_id, asset_id)

    async def content(self, series_id, asset_id):
        with Session(self.engine) as session:
            row = self._asset(session, series_id, asset_id)
            key, content_type, name = row.object_key, row.content_type, row.name
            filename = f"{row.sha256}{MEDIA_TYPES[content_type]}"
        return await self.objects.get(key), content_type, name or filename, filename

    def visual_assets(self, series_id):
        """Active images/logos a storyboard may reference."""
        return [
            {"id": item["id"], "name": item["name"], "kind": item["kind"]}
            for item in self.assets(series_id)
            if item["kind"] in VISUAL_KINDS
        ]

    def delete_series_media(self, series_id):
        """Detach rows so the series can be deleted; bytes stay in the store."""
        with Session(self.engine) as session, session.begin():
            for row in session.scalars(
                select(Asset).where(Asset.series_id == series_id)
            ):
                session.delete(row)
            for row in session.scalars(
                select(SeriesSource).where(SeriesSource.series_id == series_id)
            ):
                session.delete(row)

    # Sources ------------------------------------------------------------------

    def sources(self, series_id):
        self._require_series(series_id)
        with Session(self.engine) as session:
            rows = session.scalars(
                select(SeriesSource)
                .where(SeriesSource.series_id == series_id)
                .order_by(SeriesSource.created_at)
            )
            return [_row(row, SOURCE_KEYS) for row in rows]

    def add_source(self, series_id, source: dict):
        self._require_series(series_id)
        source_id = str(uuid4())
        try:
            with Session(self.engine) as session, session.begin():
                session.add(
                    SeriesSource(
                        id=source_id,
                        series_id=series_id,
                        source_key=source["id"],
                        url=source["url"],
                        title=source["title"],
                        excerpt=source["excerpt"],
                        created_at=now(),
                    )
                )
        except IntegrityError as exc:
            raise SeriesConflict(
                f"Source id '{source['id']}' already exists in this series"
            ) from exc
        return next(item for item in self.sources(series_id) if item["id"] == source_id)

    def delete_source(self, series_id, source_id):
        with Session(self.engine) as session, session.begin():
            row = session.get(SeriesSource, source_id)
            if row is None or row.series_id != series_id:
                raise SeriesNotFound("Source not found in this series")
            session.delete(row)

    def job_sources(self, series_id, source_ids):
        """Copy library excerpts into job source dicts (a snapshot, not a reference)."""
        library = {item["id"]: item for item in self.sources(series_id)}
        missing = [item for item in source_ids if item not in library]
        if missing:
            raise SeriesNotFound(f"Library sources not found: {', '.join(missing)}")
        return [
            {
                "id": library[item]["source_key"],
                "url": library[item]["url"],
                "title": library[item]["title"],
                "excerpt": library[item]["excerpt"],
            }
            for item in source_ids
        ]

    # Lookups ------------------------------------------------------------------

    def _require_series(self, series_id):
        with Session(self.engine) as session:
            if session.get(Series, series_id) is None:
                raise SeriesNotFound("Series not found")

    def _asset(self, session, series_id, asset_id):
        row = session.get(Asset, asset_id)
        if row is None or row.series_id != series_id:
            raise SeriesNotFound("Asset not found in this series")
        return row

    def _by_key(self, key):
        with Session(self.engine) as session:
            row = session.scalars(select(Asset).where(Asset.object_key == key)).first()
            return _row(row, ASSET_KEYS) if row else None
