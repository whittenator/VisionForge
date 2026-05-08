from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EvaluationCreate(BaseModel):
    artifact_id: str
    dataset_version_id: str
    # Filter assets by label_status; default labeled only.
    split: str = "test"  # "test" | "val" | "all"
    cluster_id: str | None = None
    iou_threshold: float = 0.5
    score_threshold: float = 0.25
    max_samples: int = 0  # 0 = no cap
    # Sample budget for FP/FN viewer; 0 disables.
    sample_fpfn_count: int = 50


class PerClass(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int
    ap50: float | None = None


class FpFnSample(BaseModel):
    asset_id: str
    predicted: str | None = None
    ground_truth: str | None = None
    score: float | None = None
    kind: str  # "fp" | "fn" | "match"


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    artifact_id: str
    dataset_version_id: str
    cluster_id: str | None = None
    job_id: str | None = None
    status: str
    metrics: dict[str, Any] | None = None
    per_class: dict[str, PerClass] | None = None
    confusion: list[list[int]] | None = None
    classes: list[str] | None = None
    samples: list[FpFnSample] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class EvaluationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_id: str
    dataset_version_id: str
    status: str
    primary_metric: float | None = None
    primary_metric_name: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
