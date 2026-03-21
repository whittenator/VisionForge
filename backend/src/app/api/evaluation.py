from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db, get_current_user
from app.models.user import User
from app.services.evaluation_service import launch_evaluation, get_evaluation

router = APIRouter(prefix="/api/experiments/runs", tags=["evaluation"])


@router.post("/{run_id}/evaluate")
def trigger_evaluation(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Launch an async evaluation job for a completed training run."""
    try:
        job = launch_evaluation(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"job_id": job.id, "status": job.status}


@router.get("/{run_id}/evaluation")
def get_evaluation_results(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return stored evaluation results for a run (null if not yet evaluated)."""
    result = get_evaluation(db, run_id)
    if result is None:
        return {"status": "not_evaluated", "summary": None, "per_class": [], "confusion_matrix": None}
    return result
