from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtifactCreate(BaseModel):
    experiment_id: str
    kind: str
    uri: str
    size_bytes: int | None = None
    checksum: str | None = None
    metadata_json: str | None = None
    stage: str = "candidate"
    version: str | None = None


class Artifact(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_id: str
    kind: str
    uri: str
    size_bytes: int | None = None
    checksum: str | None = None
    metadata_json: str | None = None
    stage: str
    version: str | None = None
    created_at: datetime | None = None
