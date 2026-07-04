from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db, security
from app.models.experiment import ExperimentRun as ExperimentModel
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Membership, Role
from app.schemas.experiment import Experiment as ExperimentSchema
from app.schemas.experiment import ExperimentCreate
from app.services import authz

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


def _member_workspace_ids(db: Session, user: User) -> list[str]:
    ws_ids = {
        m.workspace_id
        for m in db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    }
    ws_ids.add(authz.DEFAULT_WORKSPACE_ID)
    return list(ws_ids)


def _run_to_schema(e: ExperimentModel) -> ExperimentSchema:
    return ExperimentSchema(
        id=e.id,
        project_id=e.project_id,
        name=e.name,
        params_json=e.params_json,
        dataset_version_id=e.dataset_version_id,
        metrics_json=e.metrics_json,
        artifacts=e.artifacts,
        status=e.status,
        code_hash=e.code_hash,
        started_at=e.started_at,
        completed_at=e.completed_at,
        created_at=e.created_at,
    )


@router.get("/runs")
def list_runs(
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(ExperimentModel)
    if project_id:
        authz.require_project_access(db, current_user, project_id, Role.VIEWER)
        base = base.where(ExperimentModel.project_id == project_id)
    elif not authz.is_superuser(db, current_user):
        base = base.join(Project, ExperimentModel.project_id == Project.id).where(
            Project.workspace_id.in_(_member_workspace_ids(db, current_user))
        )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            base.order_by(ExperimentModel.created_at.desc()).offset(offset).limit(page_size)
        ).all()
    )
    return {
        "items": [_run_to_schema(e).model_dump() for e in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{runId}", response_model=ExperimentSchema)
def get_run(
    runId: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    e = db.get(ExperimentModel, runId)
    if not e:
        raise HTTPException(status_code=404, detail="Run not found")
    authz.require_project_access(db, current_user, e.project_id, Role.VIEWER)
    return _run_to_schema(e)


@router.post("/runs", response_model=ExperimentSchema, status_code=201)
def create_run(
    body: ExperimentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_project_access(db, current_user, body.project_id, Role.DEVELOPER)
    run = ExperimentModel(
        project_id=body.project_id,
        dataset_version_id=body.dataset_version_id,
        owner_id=current_user.id,
        name=body.name,
        status="queued",
        params_json=json.dumps(body.params) if body.params else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_to_schema(run)


def _build_metrics_payload(run_id: str, e: ExperimentModel) -> dict:
    """Parse an ``ExperimentRun``'s ``metrics_json`` into the metrics response shape.

    Shared by :func:`get_metrics` (the JSON snapshot) and the SSE stream so the two
    can't drift. ``metrics_json`` may be:
      - a list of epoch dicts: ``[{epoch, mAP50, ...}, ...]``
      - ``{"epochs": [...], "summary": {...}, "plots": [...], "split": {...}}``
      - ``{"error": "..."}`` on failure
    """
    metrics: list = []
    summary: dict | None = None
    plots: list = []
    split: dict | None = None
    if e.metrics_json:
        try:
            data = json.loads(e.metrics_json)
            if isinstance(data, list):
                metrics = data
            elif isinstance(data, dict):
                if "epochs" in data and isinstance(data["epochs"], list):
                    metrics = data["epochs"]
                elif "error" not in data:
                    metrics = [data]
                summary = data.get("summary")
                plots = data.get("plots") or []
                split = data.get("split")
        except Exception:
            pass

    # Attach presigned GET urls so the frontend can render plots in <img> tags
    # without forwarding the auth header (mirrors asset download_url).
    if plots:
        plots = [dict(p) for p in plots]
        try:
            import os
            from datetime import timedelta

            from app.services import storage

            client = storage.get_minio_client()
            bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
            for p in plots:
                if p.get("key"):
                    try:
                        p["url"] = client.presigned_get_object(
                            bucket, p["key"], expires=timedelta(hours=1)
                        )
                    except Exception:
                        p["url"] = None
        except Exception:
            pass
    return {
        "run_id": run_id,
        "status": e.status,
        "metrics": metrics,
        "summary": summary,
        "plots": plots,
        "split": split,
    }


@router.get("/runs/{runId}/metrics")
def get_metrics(
    runId: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return per-epoch metrics for live chart display."""
    e = db.get(ExperimentModel, runId)
    if not e:
        raise HTTPException(status_code=404, detail="Run not found")
    authz.require_project_access(db, current_user, e.project_id, Role.VIEWER)
    return _build_metrics_payload(runId, e)


_TERMINAL_STATUSES = ("succeeded", "failed", "cancelled")


@router.get("/runs/{runId}/metrics/stream")
async def stream_metrics(
    runId: str = Path(...),
    token: str | None = Query(None),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Server-Sent Events stream of live per-epoch metrics for a run.

    Auth mirrors the job stream in ``main.py``: a standard ``Authorization: Bearer``
    header, or a ``?token=`` query parameter for ``EventSource`` clients (which
    cannot set headers). Each tick re-reads the run's metrics from a short-lived DB
    session and emits ``data: {json}`` with the same shape as ``get_metrics`` — only
    when the payload changed. A final event carrying ``done: true`` is emitted once
    the run reaches a terminal state.
    """
    from app.db.session import SessionLocal
    from app.services.auth import get_current_user_from_token

    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_current_user_from_token(raw_token, db)
    run = db.get(ExperimentModel, runId)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    authz.require_project_access(db, user, run.project_id, Role.VIEWER)

    async def event_generator():
        last_payload: dict | None = None
        for _ in range(300):  # ~10 minutes at a 2s interval
            # Short-lived session per tick — never hold the request-scoped
            # session open across an ``await``.
            with SessionLocal() as tick_db:
                e = tick_db.get(ExperimentModel, runId)
                if not e:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    break
                payload = _build_metrics_payload(runId, e)
                status = e.status
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n"
                last_payload = payload
            if status in _TERMINAL_STATUSES:
                yield f"data: {json.dumps({**payload, 'done': True})}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/runs/{runId}/plots/{name}")
def get_plot(
    runId: str = Path(...),
    name: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a training plot PNG/JPEG that was generated by the run."""
    import os

    from fastapi.responses import StreamingResponse

    e = db.get(ExperimentModel, runId)
    if e:
        authz.require_project_access(db, current_user, e.project_id, Role.VIEWER)
    if not e or not e.metrics_json:
        raise HTTPException(status_code=404, detail="Run or plots not found")
    try:
        plots = json.loads(e.metrics_json).get("plots") or []
    except Exception:
        plots = []
    record = next((p for p in plots if p.get("name") == name or p.get("file") == name), None)
    if not record:
        raise HTTPException(status_code=404, detail="Plot not found")

    key = record["key"]
    try:
        from app.services import storage

        client = storage.get_minio_client()
        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        data = storage.get_bytes(client, key, bucket=bucket)
    except Exception as exc:  # pragma: no cover - storage failure path
        raise HTTPException(status_code=502, detail=f"could not fetch plot: {exc}") from exc

    ext = key.rsplit(".", 1)[-1].lower()
    media = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    import io as _io

    return StreamingResponse(_io.BytesIO(data), media_type=media)
