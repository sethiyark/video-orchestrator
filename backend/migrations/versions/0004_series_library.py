"""Series libraries: shared media on `assets` and reusable source excerpts."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("assets") as batch:
        batch.add_column(sa.Column("series_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("name", sa.String(200), nullable=True))
        batch.create_foreign_key("fk_assets_series_id", "series", ["series_id"], ["id"])
        batch.create_index("ix_assets_series_id", ["series_id"])
    op.create_table(
        "series_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "series_id", sa.String(36), sa.ForeignKey("series.id"), nullable=False
        ),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("series_id", "source_key"),
    )
    op.create_index("ix_series_sources_series_id", "series_sources", ["series_id"])


def downgrade():
    op.drop_table("series_sources")
    with op.batch_alter_table("assets") as batch:
        batch.drop_index("ix_assets_series_id")
        batch.drop_constraint("fk_assets_series_id", type_="foreignkey")
        batch.drop_column("name")
        batch.drop_column("series_id")
