from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
    )

    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=16), nullable=False),
    )

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id"), nullable=False),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_version_id", sa.String(length=64), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("uri", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("assets")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("projects")
