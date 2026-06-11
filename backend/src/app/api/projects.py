from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.dataset import Dataset
from app.models.project import Project as ProjectModel
from app.models.user import User
from app.models.workspace import Membership, Role, Workspace
from app.services.authz import require_project_access, require_workspace_access
from app.services.project_dataset_service import (
    VALID_TASK_TYPES,
)
from app.services.project_dataset_service import create_dataset as svc_create_dataset
from app.services.project_dataset_service import create_project as svc_create_project

router = APIRouter(prefix="/api", tags=["projects"])

_DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    workspace_id: str | None = None
    task_type: str | None = Field(
        default=None,
        description="'detect' or 'classify'. Leave unset for legacy projects.",
    )


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    task_type: str | None = None


class WizardClassSpec(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class ProjectWizard(BaseModel):
    """Single-shot endpoint that powers the multi-step new-project wizard.

    Creates the project, an initial dataset with its first version, and the
    project ClassMap in one transaction so partial state never leaks to the UI.
    """

    name: str
    description: str | None = None
    workspace_id: str | None = None
    task_type: str
    dataset_name: str = "default"
    dataset_description: str | None = None
    classes: list[WizardClassSpec] = Field(default_factory=list)


def _list_class_names(items: list[WizardClassSpec]) -> list[str]:
    return [c.name for c in items]


@router.get("/projects")
def list_projects(
    workspace_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = list(
        db.scalars(select(Membership).where(Membership.user_id == current_user.id)).all()
    )
    ws_ids = list({m.workspace_id for m in memberships} | {_DEFAULT_WORKSPACE_ID})

    base = select(ProjectModel)
    if workspace_id:
        require_workspace_access(db, current_user, workspace_id)
        base = base.where(ProjectModel.workspace_id == workspace_id)
    else:
        base = base.where(ProjectModel.workspace_id.in_(ws_ids))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            base.order_by(ProjectModel.created_at.desc()).offset(offset).limit(page_size)
        ).all()
    )
    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "workspace_id": p.workspace_id,
                "status": p.status,
                "task_type": p.task_type,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/projects/{project_id}")
def get_project(
    project_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = require_project_access(db, current_user, project_id)
    datasets = list(db.scalars(select(Dataset).where(Dataset.project_id == project_id)).all())
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "workspace_id": p.workspace_id,
        "status": p.status,
        "task_type": p.task_type,
        "dataset_count": len(datasets),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_id = payload.workspace_id or _DEFAULT_WORKSPACE_ID
    ws = db.get(Workspace, workspace_id)
    if not ws:
        workspace_id = _DEFAULT_WORKSPACE_ID
    require_workspace_access(db, current_user, workspace_id, Role.DEVELOPER)

    if payload.task_type is not None and payload.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"task_type must be one of {list(VALID_TASK_TYPES)}",
        )

    try:
        p = svc_create_project(
            db,
            payload.name,
            payload.description,
            task_type=payload.task_type,
            workspace_id=workspace_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "workspace_id": p.workspace_id,
        "status": p.status,
        "task_type": p.task_type,
    }


@router.patch("/projects/{project_id}")
def update_project(
    payload: ProjectUpdate,
    project_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = require_project_access(db, current_user, project_id, Role.DEVELOPER)
    if payload.task_type is not None and payload.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"task_type must be one of {list(VALID_TASK_TYPES)}",
        )
    if payload.name is not None:
        p.name = payload.name
    if payload.description is not None:
        p.description = payload.description
    if payload.task_type is not None:
        p.task_type = payload.task_type
    db.add(p)
    db.commit()
    db.refresh(p)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "task_type": p.task_type,
    }


@router.post("/projects/wizard", status_code=201)
def project_wizard(
    payload: ProjectWizard,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Multi-step wizard endpoint. See ``ProjectWizard`` for fields.

    All four objects (project, dataset, initial version, class map) are
    created in a single DB transaction. If any step fails the whole thing
    rolls back, so we never leak a half-built project to the UI.
    """
    if payload.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"task_type must be one of {list(VALID_TASK_TYPES)}",
        )

    workspace_id = payload.workspace_id or _DEFAULT_WORKSPACE_ID
    ws = db.get(Workspace, workspace_id)
    if not ws:
        workspace_id = _DEFAULT_WORKSPACE_ID
    require_workspace_access(db, current_user, workspace_id, Role.DEVELOPER)

    import json as _json

    from app.models.dataset import ClassMap

    try:
        project = svc_create_project(
            db,
            payload.name,
            payload.description,
            task_type=payload.task_type,
            workspace_id=workspace_id,
            commit=False,
        )

        dataset, version = svc_create_dataset(
            db,
            project.id,
            payload.dataset_name or "default",
            payload.dataset_description,
            task_type=payload.task_type,
            commit=False,
        )

        if payload.classes:
            cm = ClassMap(
                project_id=project.id,
                classes=_json.dumps(_list_class_names(payload.classes)),
            )
            db.add(cm)
            db.flush()
            dataset.class_map_id = cm.id
            db.add(dataset)
            db.flush()

        db.commit()
        db.refresh(project)
        db.refresh(dataset)
        db.refresh(version)
    except Exception:
        db.rollback()
        raise

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "task_type": project.task_type,
        },
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "task_type": dataset.task_type,
        },
        "version": {"id": version.id, "version": version.version},
        "classes": _list_class_names(payload.classes),
    }


@router.get("/projects/{project_id}/datasets")
def list_project_datasets(
    project_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user, project_id)
    datasets = list(db.scalars(select(Dataset).where(Dataset.project_id == project_id)).all())
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "task_type": d.task_type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]
