from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.dataset import Dataset
from app.models.project import Project as ProjectModel
from app.models.user import User
from app.models.workspace import Membership, Workspace
from app.services.project_dataset_service import create_project as svc_create_project

router = APIRouter(prefix="/api", tags=["projects"])

_DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    workspace_id: str | None = None


@router.get("/projects")
def list_projects(
    workspace_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gather workspace IDs the user belongs to
    memberships = list(
        db.scalars(select(Membership).where(Membership.user_id == current_user.id)).all()
    )
    ws_ids = list({m.workspace_id for m in memberships} | {_DEFAULT_WORKSPACE_ID})

    q = select(ProjectModel).where(ProjectModel.workspace_id.in_(ws_ids))
    if workspace_id:
        q = select(ProjectModel).where(ProjectModel.workspace_id == workspace_id)

    rows = list(db.scalars(q).all())
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "workspace_id": p.workspace_id,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]


@router.get("/projects/{project_id}")
def get_project(
    project_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.get(ProjectModel, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    datasets = list(
        db.scalars(select(Dataset).where(Dataset.project_id == project_id)).all()
    )
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "workspace_id": p.workspace_id,
        "status": p.status,
        "dataset_count": len(datasets),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Resolve workspace_id: use provided or fall back to default
    workspace_id = payload.workspace_id or _DEFAULT_WORKSPACE_ID
    ws = db.get(Workspace, workspace_id)
    if not ws:
        workspace_id = _DEFAULT_WORKSPACE_ID

    p = svc_create_project(db, payload.name, payload.description)
    # Update workspace_id if it differs from the service default
    if p.workspace_id != workspace_id:
        p.workspace_id = workspace_id
        db.add(p)
        db.commit()
        db.refresh(p)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "workspace_id": p.workspace_id,
        "status": p.status,
    }


@router.get("/projects/{project_id}/datasets")
def list_project_datasets(
    project_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = list(
        db.scalars(select(Dataset).where(Dataset.project_id == project_id)).all()
    )
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]
