"""Add pgvector embedding column to assets; normalize label_status spelling.

Embeddings were previously serialized into ``assets.meta_data`` JSON, which
made similarity search / duplicate detection impossible without a full-table
scan. This adds a real ``vector(512)`` column (ViT-B-32 dim) with an ANN
index. On databases without the pgvector extension (SQLite tests, stock
postgres images) the column degrades to text storage.

Also rewrites the legacy UK spelling ``unlabelled`` to ``unlabeled`` so exact
status filters behave consistently.

Revision ID: 0009_asset_embedding_pgvector
Revises: 0008_training_framework
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_asset_embedding_pgvector"
down_revision = "0008_training_framework"
branch_labels = None
depends_on = None

_DIM = 512


def _pgvector_available(bind) -> bool:
    if bind.dialect.name != "postgresql":
        return False
    row = bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).first()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _pgvector_available(bind):
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(f"ALTER TABLE assets ADD COLUMN IF NOT EXISTS embedding vector({_DIM})")
        # HNSW needs pgvector >= 0.5; fall back to ivfflat on older builds.
        try:
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_assets_embedding "
                "ON assets USING hnsw (embedding vector_cosine_ops)"
            )
        except Exception:
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_assets_embedding "
                "ON assets USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )
    else:
        op.add_column("assets", sa.Column("embedding", sa.Text(), nullable=True))

    op.execute("UPDATE assets SET label_status = 'unlabeled' WHERE label_status = 'unlabelled'")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_assets_embedding")
    op.drop_column("assets", "embedding")
