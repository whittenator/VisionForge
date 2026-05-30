"""Add training-framework columns; merge the cluster-discovery + phase2 heads.

The migration tree had two open heads (``0004_cluster_discovery`` and
``0007_phase2_task_type_and_review``). This revision merges them into a single
head so ``alembic upgrade head`` is unambiguous, and adds the nullable
``framework`` column to ``experiment_runs`` and ``model_artifacts`` used by the
pluggable training backends (Ultralytics / Timm / …).

Revision ID: 0008_training_framework
Revises: 0004_cluster_discovery, 0007_phase2_task_type_and_review
Create Date: 2026-05-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_training_framework"
down_revision = ("0004_cluster_discovery", "0007_phase2_task_type_and_review")
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("experiment_runs") as batch:
        batch.add_column(sa.Column("framework", sa.String(length=32), nullable=True))
    with op.batch_alter_table("model_artifacts") as batch:
        batch.add_column(sa.Column("framework", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("model_artifacts") as batch:
        batch.drop_column("framework")
    with op.batch_alter_table("experiment_runs") as batch:
        batch.drop_column("framework")
