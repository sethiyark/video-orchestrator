from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .base import Base


class Series(Base):
    __tablename__ = "series"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeriesBibleVersion(Base):
    """Append-only bible history; the highest version is current."""

    __tablename__ = "series_bibles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("series_id", "version"),)


class SeriesTheme(Base):
    __tablename__ = "series_themes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    blurb: Mapped[str] = mapped_column(Text, default="")
    guidance: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeriesIdea(Base):
    __tablename__ = "series_ideas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"), index=True)
    theme_id: Mapped[str | None] = mapped_column(
        ForeignKey("series_themes.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    pitch: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), index=True)
    # No FK: deleting a job resets the idea instead of failing.
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeriesSource(Base):
    """Reusable evidence excerpt; jobs copy it at creation, never reference it."""

    __tablename__ = "series_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(300))
    excerpt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("series_id", "source_key"),)
