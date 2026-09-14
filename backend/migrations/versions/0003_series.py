"""Series: shared bibles, themes, and idea backlogs for video jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade():
    op.create_table(
        "series",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_series_created_at", "series", ["created_at"])
    op.create_table(
        "series_bibles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "series_id", sa.String(36), sa.ForeignKey("series.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("series_id", "version"),
    )
    op.create_index("ix_series_bibles_series_id", "series_bibles", ["series_id"])
    op.create_table(
        "series_themes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "series_id", sa.String(36), sa.ForeignKey("series.id"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("blurb", sa.Text(), nullable=False),
        sa.Column("guidance", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_series_themes_series_id", "series_themes", ["series_id"])
    op.create_table(
        "series_ideas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "series_id", sa.String(36), sa.ForeignKey("series.id"), nullable=False
        ),
        sa.Column(
            "theme_id", sa.String(36), sa.ForeignKey("series_themes.id"), nullable=True
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("pitch", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=True),
        *_timestamps(),
    )
    for column in ("series_id", "theme_id", "status", "job_id", "created_at"):
        op.create_index(f"ix_series_ideas_{column}", "series_ideas", [column])


def downgrade():
    op.drop_table("series_ideas")
    op.drop_table("series_themes")
    op.drop_table("series_bibles")
    op.drop_table("series")
