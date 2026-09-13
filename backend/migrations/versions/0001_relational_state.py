"""Relational video state; the original jobs table remains intact for import."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "video_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("approved_at", sa.String(40)),
        sa.Column("error", sa.Text()),
        sa.Column("context", sa.JSON(), nullable=False),
    )
    op.create_index("ix_video_jobs_status", "video_jobs", ["status"])
    op.create_index("ix_video_jobs_created_at", "video_jobs", ["created_at"])
    op.create_table(
        "video_stages",
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("video_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("output", sa.JSON()),
    )
    op.create_table(
        "stage_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("video_jobs.id"), nullable=False
        ),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("ended_at", sa.String(40)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("provenance", sa.JSON(), nullable=False),
    )
    op.create_index("ix_stage_attempts_job_id", "stage_attempts", ["job_id"])


def downgrade():
    op.drop_table("stage_attempts")
    op.drop_table("video_stages")
    op.drop_table("video_jobs")
