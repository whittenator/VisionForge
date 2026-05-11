from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationJobResponse,
    EvaluationListPage,
    EvaluationOut,
    EvaluationSummary,
)
from app.services import cluster_service, evaluation_service

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("", response_model=EvaluationListPage)
def list_evaluations(
    artifact_id: str | None = Query(None),
    dataset_version_id: str | None = Query(None),
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows, total = evaluation_service.list_evaluations(
        db,
        artifact_id=artifact_id,
        dataset_version_id=dataset_version_id,
        project_id=project_id,
        page=page,
        page_size=page_size,
        return_total=True,
    )
    return EvaluationListPage(
        items=[EvaluationSummary(**evaluation_service.summarize(r)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=EvaluationJobResponse, status_code=202)
def create_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _, job = evaluation_service.create_evaluation(db, payload)
    except evaluation_service.EvaluationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except cluster_service.ClusterNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EvaluationJobResponse(**job)


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(
    evaluation_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = evaluation_service.get_evaluation(db, evaluation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return EvaluationOut(**evaluation_service.to_dict(row))
