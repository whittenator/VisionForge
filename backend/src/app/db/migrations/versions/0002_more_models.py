from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_more_models"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "annotation_schemas",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("schema_json", sa.Text, nullable=False),
        sa.Column("color_map_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "annotations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("schema_id", sa.String(length=36), sa.ForeignKey("annotation_schemas.id"), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("data_json", sa.Text, nullable=False),
        sa.Column("author_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tracks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("track_id", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.Text, nullable=False),
    )

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("params_json", sa.Text, nullable=True),
        sa.Column("dataset_version_id", sa.String(length=64), sa.ForeignKey("dataset_versions.id"), nullable=True),
        sa.Column("metrics_json", sa.Text, nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("experiment_id", sa.String(length=36), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("uri", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "al_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("params_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "al_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("al_run_id", sa.String(length=36), sa.ForeignKey("al_runs.id"), nullable=False),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("priority", sa.Float, nullable=False),
        sa.Column("proposed_json", sa.Text, nullable=True),
        sa.Column("resolved_status", sa.String(length=16), nullable=False),
        sa.Column("resolved_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Float, nullable=False),
        sa.Column("logs_uri", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("entity", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("diff_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audits")
    op.drop_table("jobs")
    op.drop_table("al_items")
    op.drop_table("al_runs")
    op.drop_table("artifacts")
    op.drop_table("experiments")
    op.drop_table("tracks")
    op.drop_table("annotations")
    op.drop_table("annotation_schemas")
    op.drop_table("memberships")
    op.drop_table("users")
