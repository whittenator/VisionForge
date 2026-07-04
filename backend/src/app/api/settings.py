from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.models.workspace import Role, Workspace
from app.schemas.settings import (
    StorageSettingsResponse,
    StorageSettingsUpdate,
    StorageTestResult,
)
from app.services import storage_backends
from app.services.authz import require_workspace_access

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_BACKENDS: tuple[str, ...] = storage_backends.VALID_BACKENDS


def _load_workspace(db: Session, workspace_id: str) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


def _stored_config(ws: Workspace) -> dict[str, Any]:
    if not ws.storage_config:
        return {}
    try:
        parsed = json.loads(ws.storage_config)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _merge_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge ``incoming`` over ``existing``, preserving the stored secret key
    when the caller omits it."""
    merged = dict(existing)
    merged.update(incoming)
    if not incoming.get("secret_key") and existing.get("secret_key"):
        merged["secret_key"] = existing["secret_key"]
    return merged


@router.get("/workspaces/{workspace_id}/storage", response_model=StorageSettingsResponse)
def get_storage_settings(
    workspace_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageSettingsResponse:
    require_workspace_access(db, current_user, workspace_id, Role.ADMIN)
    ws = _load_workspace(db, workspace_id)
    settings = storage_backends.resolve_workspace_storage(db, workspace_id)
    return StorageSettingsResponse(
        backend=ws.storage_backend or settings.backend,
        config=storage_backends.public_config(settings),
    )


@router.put("/workspaces/{workspace_id}/storage", response_model=StorageSettingsResponse)
def update_storage_settings(
    body: StorageSettingsUpdate,
    workspace_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageSettingsResponse:
    require_workspace_access(db, current_user, workspace_id, Role.OWNER)
    ws = _load_workspace(db, workspace_id)

    if body.backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid backend '{body.backend}'; must be one of {list(VALID_BACKENDS)}",
        )

    existing = _stored_config(ws)
    incoming = body.config.model_dump(exclude_none=True) if body.config else {}
    merged = _merge_config(existing, incoming)

    ws.storage_backend = body.backend
    ws.storage_config = json.dumps(merged)
    db.add(ws)
    db.commit()
    db.refresh(ws)

    settings = storage_backends.resolve_workspace_storage(db, workspace_id)
    return StorageSettingsResponse(
        backend=ws.storage_backend,
        config=storage_backends.public_config(settings),
    )


@router.post("/workspaces/{workspace_id}/storage/test", response_model=StorageTestResult)
def test_storage_settings(
    workspace_id: str = Path(...),
    body: StorageSettingsUpdate | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageTestResult:
    require_workspace_access(db, current_user, workspace_id, Role.ADMIN)
    ws = _load_workspace(db, workspace_id)

    if body is not None:
        backend = (
            body.backend if body.backend in VALID_BACKENDS else (ws.storage_backend or "minio")
        )
        existing = _stored_config(ws)
        incoming = body.config.model_dump(exclude_none=True) if body.config else {}
        merged = _merge_config(existing, incoming)
        settings = storage_backends.settings_from(backend, merged)
    else:
        settings = storage_backends.resolve_workspace_storage(db, workspace_id)

    ok, detail = storage_backends.test_connection(settings)
    return StorageTestResult(ok=ok, detail=detail)
