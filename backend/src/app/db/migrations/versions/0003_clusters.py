"""Add clusters table and experiment_runs.cluster_id

Revision ID: 0003_clusters
Revises: 0002_add_missing_columns
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_clusters"
down_revision = "0002_add_missing_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clusters",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="both"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="offline"),
        sa.Column("cpu_cores", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ram_total_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disk_total_gb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpu_vendor", sa.String(length=16), nullable=False, server_default="cpu"),
        sa.Column("gpu_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpu_model", sa.String(length=255), nullable=True),
        sa.Column("gpu_memory_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpus_json", sa.Text(), nullable=True),
        sa.Column("cpu_usage_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ram_used_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disk_used_gb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpu_usage_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("active_job_id", sa.String(length=36), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("register_token", sa.String(length=64), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_clusters_status", "clusters", ["status"])
    op.create_index("ix_clusters_kind", "clusters", ["kind"])

    op.add_column(
        "experiment_runs",
        sa.Column("cluster_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_experiment_runs_cluster_id",
        "experiment_runs",
        "clusters",
        ["cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_experiment_runs_cluster_id", "experiment_runs", type_="foreignkey")
    op.drop_column("experiment_runs", "cluster_id")
    op.drop_index("ix_clusters_kind", table_name="clusters")
    op.drop_index("ix_clusters_status", table_name="clusters")
    op.drop_table("clusters")
