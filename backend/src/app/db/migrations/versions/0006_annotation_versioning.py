"""Add annotation.version and annotation.updated_at for optimistic locking.

Revision ID: 0006_annotation_versioning
Revises: 0005_evaluations
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_annotation_versioning"
down_revision = "0005_evaluations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "annotations",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "annotations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("annotations", "updated_at")
    op.drop_column("annotations", "version")
