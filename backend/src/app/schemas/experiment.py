from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ExperimentCreate(BaseModel):
    project_id: str
    name: str
    dataset_version_id: str | None = None
    params: dict[str, Any] | None = None


class Experiment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    dataset_version_id: str | None = None
    params_json: str | None = None
    metrics_json: str | None = None
    status: str
    code_hash: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class MetricsUpdate(BaseModel):
    epoch: int
    metrics: dict[str, float]
