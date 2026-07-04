from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StorageConfigIn(BaseModel):
    """Inbound storage configuration. All fields optional so partial updates
    (e.g. omitting ``secret_key`` to preserve the stored one) are possible."""

    model_config = ConfigDict(extra="ignore")

    endpoint: str | None = None
    region: str | None = None
    bucket: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    secure: bool | None = None


class StorageSettingsUpdate(BaseModel):
    backend: str
    config: StorageConfigIn = StorageConfigIn()


class StorageSettingsResponse(BaseModel):
    backend: str
    config: dict[str, Any]


class StorageTestResult(BaseModel):
    ok: bool
    detail: str
