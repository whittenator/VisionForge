"""Feature columns: workspace storage config, run checkpoints, AL retrain link.

Adds:
- workspaces.storage_backend / storage_config — per-workspace object-storage
  selection (MinIO vs S3) and its settings blob.
- experiment_runs.checkpoints — JSON list of intermediate training checkpoints
  enabling resume.
- al_runs.last_train_run_id — links an active-learning run to the training run
  spawned from its resolved items (retrain feedback loop).

Revision ID: 0010_feature_columns
Revises: 0009_asset_embedding_pgvector
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_feature_columns"
down_revision = "0009_asset_embedding_pgvector"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "workspaces", "storage_backend"):
        op.add_column(
            "workspaces",
            sa.Column(
                "storage_backend",
                sa.String(length=20),
                nullable=False,
                server_default="minio",
            ),
        )
    if not _has_column(bind, "workspaces", "storage_config"):
        op.add_column("workspaces", sa.Column("storage_config", sa.Text(), nullable=True))
    if not _has_column(bind, "experiment_runs", "checkpoints"):
        op.add_column("experiment_runs", sa.Column("checkpoints", sa.Text(), nullable=True))
    if not _has_column(bind, "al_runs", "last_train_run_id"):
        op.add_column(
            "al_runs", sa.Column("last_train_run_id", sa.String(length=36), nullable=True)
        )


def downgrade() -> None:
    op.drop_column("al_runs", "last_train_run_id")
    op.drop_column("experiment_runs", "checkpoints")
    op.drop_column("workspaces", "storage_config")
    op.drop_column("workspaces", "storage_backend")
