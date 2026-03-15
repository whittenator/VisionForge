from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.experiment import ExperimentRun
from app.services.evaluation_service import launch_evaluation

router = APIRouter(prefix="/api/experiments/runs", tags=["evaluation"])


@router.post("/{run_id}/evaluate")
def trigger_evaluation(
    run_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    run = db.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "succeeded":
        raise HTTPException(status_code=400, detail="Can only evaluate succeeded runs")
    job = launch_evaluation(db, run_id)
    return {"job_id": job.id, "status": job.status}


@router.get("/{run_id}/evaluation")
def get_evaluation(
    run_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    run = db.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.evaluation_json:
        raise HTTPException(
            status_code=404,
            detail="No evaluation results yet. Run POST /evaluate first.",
        )
    try:
        return json.loads(run.evaluation_json)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid evaluation data stored")
