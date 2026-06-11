from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.artifact import ModelArtifact
from app.models.dataset_version import DatasetVersion
from app.models.evaluation import Evaluation
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Membership, Role
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationJobResponse,
    EvaluationListPage,
    EvaluationOut,
    EvaluationSummary,
)
from app.services import authz, cluster_service, evaluation_service

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _member_workspace_ids(db: Session, user: User) -> list[str]:
    ws_ids = {
        m.workspace_id
        for m in db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    }
    ws_ids.add(authz.DEFAULT_WORKSPACE_ID)
    return list(ws_ids)


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
    # Enforce access on every filter the caller supplied.
    if project_id:
        authz.require_project_access(db, current_user, project_id, Role.VIEWER)
    if artifact_id:
        artifact = db.get(ModelArtifact, artifact_id)
        if artifact is not None:
            authz.require_project_access(db, current_user, artifact.project_id, Role.VIEWER)
    if dataset_version_id:
        version = db.get(DatasetVersion, dataset_version_id)
        if version is not None:
            authz.require_dataset_access(db, current_user, version.dataset_id, Role.VIEWER)

    # Unfiltered listing: scope to the caller's workspaces (superusers see all).
    if (
        not project_id
        and not artifact_id
        and not dataset_version_id
        and not authz.is_superuser(db, current_user)
    ):
        q = (
            select(Evaluation)
            .join(Project, Evaluation.project_id == Project.id)
            .where(Project.workspace_id.in_(_member_workspace_ids(db, current_user)))
            .order_by(Evaluation.created_at.desc())
        )
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        offset = max(0, (page - 1) * page_size)
        rows = list(db.scalars(q.offset(offset).limit(page_size)).all())
        return EvaluationListPage(
            items=[EvaluationSummary(**evaluation_service.summarize(r)) for r in rows],
            total=int(total),
            page=page,
            page_size=page_size,
        )

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
    # Missing artifact/version is left to the service (it raises 400-mapped
    # EvaluationError); when they resolve, enforce developer access.
    artifact = db.get(ModelArtifact, payload.artifact_id)
    if artifact is not None:
        authz.require_project_access(db, current_user, artifact.project_id, Role.DEVELOPER)
    version = db.get(DatasetVersion, payload.dataset_version_id)
    if version is not None:
        authz.require_dataset_access(db, current_user, version.dataset_id, Role.DEVELOPER)
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
    authz.require_project_access(db, current_user, row.project_id, Role.VIEWER)
    return EvaluationOut(**evaluation_service.to_dict(row))
