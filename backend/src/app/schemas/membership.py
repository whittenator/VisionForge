from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MembershipCreate(BaseModel):
    project_id: str
    user_id: str
    role: str = "annotator"


class Membership(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    user_id: str
    role: str
    created_at: datetime | None = None
