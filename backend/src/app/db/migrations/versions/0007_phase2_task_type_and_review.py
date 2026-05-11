"""Add Project/Dataset task_type, annotation review workflow fields.

Adds the columns Phase 2 needs:
  * `projects.task_type`     — "detect" | "classify" (or NULL legacy)
  * `datasets.task_type`     — same enum, denormalised on the dataset
  * `annotations.review_status`   — "unreviewed" | "approved" | "rejected"
  * `annotations.reviewer_id`     — FK to users.id
  * `annotations.reviewed_at`     — timestamp the review was recorded
  * `annotations.review_notes`    — free-text reviewer comment
  * `annotations.flagged`         — bool, set by the error-mining task
  * `annotations.flag_reason`     — short string set alongside `flagged`

Revision ID: 0007_phase2_task_type_and_review
Revises: 0006_annotation_versioning
Create Date: 2026-05-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_phase2_task_type_and_review"
down_revision = "0006_annotation_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("task_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "datasets",
        sa.Column("task_type", sa.String(length=32), nullable=True),
    )

    op.add_column(
        "annotations",
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="unreviewed",
        ),
    )
    op.add_column(
        "annotations",
        sa.Column(
            "reviewer_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "annotations",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "annotations",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "annotations",
        sa.Column(
            "flagged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "annotations",
        sa.Column("flag_reason", sa.String(length=255), nullable=True),
    )

    op.create_index(
        "ix_annotations_review_status",
        "annotations",
        ["review_status"],
    )
    op.create_index(
        "ix_annotations_flagged",
        "annotations",
        ["flagged"],
    )


def downgrade() -> None:
    op.drop_index("ix_annotations_flagged", table_name="annotations")
    op.drop_index("ix_annotations_review_status", table_name="annotations")
    op.drop_column("annotations", "flag_reason")
    op.drop_column("annotations", "flagged")
    op.drop_column("annotations", "review_notes")
    op.drop_column("annotations", "reviewed_at")
    op.drop_column("annotations", "reviewer_id")
    op.drop_column("annotations", "review_status")
    op.drop_column("datasets", "task_type")
    op.drop_column("projects", "task_type")
