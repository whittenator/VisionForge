from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Evaluation(Base):
    """Result of running a trained model against a dataset version split.

    Stores summary metrics (mAP, accuracy, per-class P/R/F1) plus links to a
    sample of false positives and false negatives for the FP/FN viewer UI.
    """

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_artifacts.id"), nullable=False
    )
    dataset_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id"), nullable=False
    )
    cluster_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clusters.id"), nullable=True
    )
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True)

    # "queued" | "running" | "succeeded" | "failed"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")

    # JSON: {"mAP50": 0.812, "mAP50-95": 0.643, "accuracy": 0.91, "precision": 0.87, ...}
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: {"class_name": {"precision": .., "recall": .., "f1": .., "support": .., "ap50": ..}}
    per_class_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: 2D array of counts; classes_json holds row/col labels
    confusion_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    classes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: list of {asset_id, predicted, ground_truth, score, kind: "fp"|"fn"}
    samples_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
