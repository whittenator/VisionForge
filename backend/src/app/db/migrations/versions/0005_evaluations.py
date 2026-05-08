"""Add evaluations table.

Revision ID: 0005_evaluations
Revises: 0004_force_bcrypt
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_evaluations"
down_revision = "0004_force_bcrypt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=36),
            sa.ForeignKey("model_artifacts.id"),
            nullable=False,
        ),
        sa.Column(
            "dataset_version_id",
            sa.String(length=36),
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "cluster_id",
            sa.String(length=36),
            sa.ForeignKey("clusters.id"),
            nullable=True,
        ),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("per_class_json", sa.Text(), nullable=True),
        sa.Column("confusion_json", sa.Text(), nullable=True),
        sa.Column("classes_json", sa.Text(), nullable=True),
        sa.Column("samples_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_evaluations_artifact_id", "evaluations", ["artifact_id"])
    op.create_index("ix_evaluations_dataset_version_id", "evaluations", ["dataset_version_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluations_dataset_version_id", table_name="evaluations")
    op.drop_index("ix_evaluations_artifact_id", table_name="evaluations")
    op.drop_table("evaluations")
