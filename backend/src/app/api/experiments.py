from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.experiment import Experiment as ExperimentModel
from app.schemas.experiment import Experiment as ExperimentSchema


router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("/runs", response_model=list[ExperimentSchema] | None)
def list_runs(db: Session = Depends(get_db)):
    rows = db.scalars(select(ExperimentModel)).all()
    return [
        ExperimentSchema(
            id=e.id,
            project_id=e.project_id,
            name=e.name,
            params_json=e.params_json,
            dataset_version_id=e.dataset_version_id,
            metrics_json=e.metrics_json,
            status=e.status,
            started_at=e.started_at,
            finished_at=e.finished_at,
            code_hash=e.code_hash,
        )
        for e in rows
    ]


@router.get("/runs/{runId}", response_model=ExperimentSchema)
def get_run(runId: str = Path(...), db: Session = Depends(get_db)):
    e = db.get(ExperimentModel, runId)
    if not e:
        raise HTTPException(status_code=404, detail="Run not found")
    return ExperimentSchema(
        id=e.id,
        project_id=e.project_id,
        name=e.name,
        params_json=e.params_json,
        dataset_version_id=e.dataset_version_id,
        metrics_json=e.metrics_json,
        status=e.status,
        started_at=e.started_at,
        finished_at=e.finished_at,
        code_hash=e.code_hash,
    )
