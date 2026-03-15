"""Add evaluation_json to experiment_runs, invited_by to memberships

Revision ID: 0003
Revises: 0002_add_missing_columns
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002_add_missing_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiment_runs", sa.Column("evaluation_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("experiment_runs", "evaluation_json")
