from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.experiment import ExperimentRun as ExperimentModel
from app.models.user import User
from app.schemas.experiment import Experiment as ExperimentSchema
from app.schemas.experiment import ExperimentCreate

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


def _run_to_schema(e: ExperimentModel) -> ExperimentSchema:
    return ExperimentSchema(
        id=e.id,
        project_id=e.project_id,
        name=e.name,
        params_json=e.params_json,
        dataset_version_id=e.dataset_version_id,
        metrics_json=e.metrics_json,
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
        base = base.where(ExperimentModel.project_id == project_id)
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
    return _run_to_schema(e)


@router.post("/runs", response_model=ExperimentSchema, status_code=201)
def create_run(
    body: ExperimentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    metrics: list = []
    if e.metrics_json:
        try:
            data = json.loads(e.metrics_json)
            # metrics_json may be:
            #   - a list of epoch dicts: [{epoch, mAP50, ...}, ...]
            #   - {"epochs": [{epoch, mAP50, ...}, ...]} as written by train_task
            #   - {"error": "..."} on failure
            if isinstance(data, list):
                metrics = data
            elif isinstance(data, dict):
                if "epochs" in data and isinstance(data["epochs"], list):
                    metrics = data["epochs"]
                elif "error" not in data:
                    metrics = [data]
        except Exception:
            pass
    return {"run_id": runId, "status": e.status, "metrics": metrics}
