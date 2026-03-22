from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.experiment import ExperimentRun as ExperimentModel
from app.models.user import User
from app.schemas.experiment import Experiment as ExperimentSchema, ExperimentCreate

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


@router.get("/runs", response_model=list[ExperimentSchema] | None)
def list_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.scalars(select(ExperimentModel)).all()
    return [_run_to_schema(e) for e in rows]


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
