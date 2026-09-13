from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .base import Base


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChannelConfig(Base):
    __tablename__ = "channel_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoProject(Base):
    __tablename__ = "video_projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    brief: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(40), index=True)
    format: Mapped[str] = mapped_column(String(16), default="long")
    v1_job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_video_projects_channel_state", "channel_id", "state"),)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("video_projects.id"), index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(80), index=True)
    temporal_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("video_projects.id"), index=True
    )
    series_id: Mapped[str | None] = mapped_column(ForeignKey("series.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40), index=True)
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), index=True)
    provenance: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CostRecord(Base):
    __tablename__ = "cost_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("video_projects.id"), index=True
    )
    category: Mapped[str] = mapped_column(String(40), index=True)
    vendor: Mapped[str] = mapped_column(String(80))
    amount_usd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(160))
    provider: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool]
    retry_count: Mapped[int] = mapped_column(Integer)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), index=True)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GpuJob(Base):
    __tablename__ = "gpu_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource: Mapped[str] = mapped_column(String(80), index=True)
    priority: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    extra: Mapped[dict] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
