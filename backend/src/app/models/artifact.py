from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("experiment_runs.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # pytorch, onnx
    format: Mapped[str] = mapped_column(String(32), nullable=False, default="pytorch")
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # MinIO key
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
