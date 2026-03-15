"""Add missing columns to experiment_runs, model_artifacts, users, jobs

Revision ID: 0002_add_missing_columns
Revises: 0001_initial_schema
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_missing_columns"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # experiment_runs: add name, code_hash, started_at columns
    op.add_column("experiment_runs", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("experiment_runs", sa.Column("code_hash", sa.String(64), nullable=True))
    op.add_column("experiment_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))

    # model_artifacts: add storage_path, format, name columns
    op.add_column("model_artifacts", sa.Column("storage_path", sa.String(1024), nullable=True))
    op.add_column("model_artifacts", sa.Column("format", sa.String(32), nullable=True))
    op.add_column("model_artifacts", sa.Column("name", sa.String(255), nullable=True))

    # users: add is_superuser
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), nullable=True, server_default="false"))

    # jobs: add error_message, result_json, logs_uri (if not exists)
    op.add_column("jobs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_json", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("logs_uri", sa.String(1024), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_column("jobs", "updated_at")
    op.drop_column("jobs", "logs_uri")
    op.drop_column("jobs", "result_json")
    op.drop_column("jobs", "error_message")
    op.drop_column("users", "is_superuser")
    op.drop_column("model_artifacts", "name")
    op.drop_column("model_artifacts", "format")
    op.drop_column("model_artifacts", "storage_path")
    op.drop_column("experiment_runs", "started_at")
    op.drop_column("experiment_runs", "code_hash")
    op.drop_column("experiment_runs", "name")
