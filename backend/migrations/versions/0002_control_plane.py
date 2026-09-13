"""Control-plane tables for projects, workflows, assets, costs, and GPU jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "channels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "channel_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "channel_id",
            sa.String(36),
            sa.ForeignKey("channels.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_channel_configs_channel_id", "channel_configs", ["channel_id"])
    op.create_table(
        "video_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "channel_id",
            sa.String(36),
            sa.ForeignKey("channels.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("v1_job_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_video_projects_channel_id", "video_projects", ["channel_id"])
    op.create_index("ix_video_projects_state", "video_projects", ["state"])
    op.create_index("ix_video_projects_v1_job_id", "video_projects", ["v1_job_id"])
    op.create_index("ix_video_projects_created_at", "video_projects", ["created_at"])
    op.create_index(
        "ix_video_projects_channel_state", "video_projects", ["channel_id", "state"]
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id")),
        sa.Column("workflow_type", sa.String(80), nullable=False),
        sa.Column("temporal_id", sa.String(200), unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_runs_project_id", "workflow_runs", ["project_id"])
    op.create_index(
        "ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"]
    )
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_events_run_id", "workflow_events", ["run_id"])
    op.create_index("ix_workflow_events_type", "workflow_events", ["type"])
    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id")),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index("ix_assets_kind", "assets", ["kind"])
    op.create_index("ix_assets_sha256", "assets", ["sha256"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_code", "alerts", ["code"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])
    op.create_table(
        "cost_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id")),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("vendor", sa.String(80), nullable=False),
        sa.Column("amount_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cost_records_project_id", "cost_records", ["project_id"])
    op.create_index("ix_cost_records_category", "cost_records", ["category"])
    op.create_index("ix_cost_records_created_at", "cost_records", ["created_at"])
    op.create_table(
        "model_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(36)),
        sa.Column("workflow_id", sa.String(36)),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_runs_agent", "model_runs", ["agent"])
    op.create_index("ix_model_runs_project_id", "model_runs", ["project_id"])
    op.create_index("ix_model_runs_workflow_id", "model_runs", ["workflow_id"])
    op.create_index("ix_model_runs_created_at", "model_runs", ["created_at"])
    op.create_table(
        "gpu_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_gpu_jobs_resource", "gpu_jobs", ["resource"])
    op.create_index("ix_gpu_jobs_priority", "gpu_jobs", ["priority"])
    op.create_index("ix_gpu_jobs_status", "gpu_jobs", ["status"])
    op.execute(
        sa.text(
            "INSERT INTO channels (id, slug, name, created_at, updated_at) "
            "VALUES ('00000000-0000-4000-8000-000000000001', 'engineering-explainers', "
            "'Engineering Explainers', '2026-01-01 00:00:00+00:00', '2026-01-01 00:00:00+00:00')"
        )
    )


def downgrade():
    op.drop_table("gpu_jobs")
    op.drop_table("model_runs")
    op.drop_table("cost_records")
    op.drop_table("alerts")
    op.drop_table("assets")
    op.drop_table("workflow_events")
    op.drop_table("workflow_runs")
    op.drop_table("video_projects")
    op.drop_table("channel_configs")
    op.drop_table("channels")
