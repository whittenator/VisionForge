from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import EmbeddingVector

# ViT-B-32 (open-clip) output dimension; must match EmbeddingsService.
EMBEDDING_DIM = 512


def _uuid() -> str:
    return str(uuid.uuid4())


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.id"), nullable=False)
    version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dataset_versions.id"), nullable=True
    )
    uri: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    embedding: Mapped[list[float] | None] = mapped_column(
        EmbeddingVector(EMBEDDING_DIM), nullable=True
    )
    label_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unlabeled")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
