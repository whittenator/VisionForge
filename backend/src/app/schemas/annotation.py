from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnnotationCreate(BaseModel):
    asset_id: str
    schema_id: str
    type: str
    data_json: str
    author_id: str | None = None


class Annotation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    schema_id: str
    type: str
    data_json: str
    author_id: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
