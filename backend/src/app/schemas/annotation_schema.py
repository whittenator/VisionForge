from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnnotationSchemaCreate(BaseModel):
    project_id: str
    schema_json: str
    color_map_json: str | None = None


class AnnotationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    schema_json: str
    color_map_json: str | None = None
    created_at: datetime | None = None
