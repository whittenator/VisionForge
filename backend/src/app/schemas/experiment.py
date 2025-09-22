from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExperimentCreate(BaseModel):
    project_id: str
    name: str
    params_json: str | None = None
    dataset_version_id: str | None = None


class Experiment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    params_json: str | None = None
    dataset_version_id: str | None = None
    metrics_json: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    code_hash: str | None = None
