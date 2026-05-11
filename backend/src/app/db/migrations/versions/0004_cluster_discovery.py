"""Add agent connection + OS columns to clusters for the discovery flow.

Revision ID: 0004_cluster_discovery
Revises: 0003_clusters
Create Date: 2026-05-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_cluster_discovery"
down_revision = "0003_clusters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("clusters") as batch:
        batch.add_column(sa.Column("agent_host", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("agent_port", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("agent_version", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("os_name", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("os_release", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("arch", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("clusters") as batch:
        batch.drop_column("arch")
        batch.drop_column("os_release")
        batch.drop_column("os_name")
        batch.drop_column("agent_version")
        batch.drop_column("agent_port")
        batch.drop_column("agent_host")
