from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    email: str
    name: str | None = None
    role: str = "viewer"


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None
    role: str
    created_at: datetime | None = None
