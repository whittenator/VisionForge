"""Add password_hash to users

Revision ID: 0003_user_password_hash
Revises: 0002_more_models
Create Date: 2025-09-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_user_password_hash"
down_revision = "0002_more_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
