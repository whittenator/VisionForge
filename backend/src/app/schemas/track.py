from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TrackCreate(BaseModel):
    asset_id: str
    track_id: str
    data_json: str


class Track(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    track_id: str
    data_json: str
