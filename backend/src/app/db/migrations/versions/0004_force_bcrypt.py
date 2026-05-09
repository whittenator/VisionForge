"""Invalidate any non-bcrypt password hashes (force password reset).

Revision ID: 0004_force_bcrypt
Revises: 0003_clusters
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_force_bcrypt"
down_revision = "0003_clusters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Null out any hash that doesn't look like bcrypt. Affected users will fail
    # to log in (`authenticate` returns None) and must reset via admin tool.
    bind = op.get_bind()
    bind.execute(sa.text("""
            UPDATE users
               SET password_hash = NULL
             WHERE password_hash IS NOT NULL
               AND password_hash NOT LIKE '$2a$%'
               AND password_hash NOT LIKE '$2b$%'
               AND password_hash NOT LIKE '$2y$%'
            """))


def downgrade() -> None:
    # Cannot un-null without the original plaintext.
    pass
