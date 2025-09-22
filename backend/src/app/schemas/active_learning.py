from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ALRunCreate(BaseModel):
    project_id: str
    strategy: str
    params_json: str | None = None


class ALRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    strategy: str
    params_json: str | None = None
    created_at: datetime | None = None


class ALItemCreate(BaseModel):
    al_run_id: str
    asset_id: str
    priority: float = 0.0
    proposed_json: str | None = None


class ALItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    al_run_id: str
    asset_id: str
    priority: float
    proposed_json: str | None = None
    resolved_status: str
    resolved_by: str | None = None
    resolved_at: datetime | None = None
