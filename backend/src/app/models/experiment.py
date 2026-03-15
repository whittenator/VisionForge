from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    dataset_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dataset_versions.id"), nullable=True
    )
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Unnamed Run")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    params_json: Mapped[str | None] = mapped_column("params", Text, nullable=True)  # DB column "params" mapped to params_json
    metrics_json: Mapped[str | None] = mapped_column("metrics", Text, nullable=True)  # DB column "metrics" mapped to metrics_json
    artifacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
