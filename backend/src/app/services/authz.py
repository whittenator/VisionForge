from __future__ import annotations

import os

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Membership, Role, Workspace

# Shared workspace that every authenticated user can access (legacy projects
# and projects created without an explicit workspace land here).
DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"

ROLE_ORDER: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.ANNOTATOR: 1,
    Role.DEVELOPER: 2,
    Role.ADMIN: 3,
    Role.OWNER: 4,
}


def is_superuser(db: Session, user: User) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    superuser_email = os.getenv("FIRST_SUPERUSER_EMAIL") or os.getenv("SUPERUSER_EMAIL")
    return bool(superuser_email and user.email == superuser_email)


def _role_level(role: object) -> int:
    if isinstance(role, Role):
        return ROLE_ORDER.get(role, -1)
    try:
        return ROLE_ORDER.get(Role(str(role)), -1)
    except ValueError:
        return -1


def get_membership(db: Session, user: User, workspace_id: str) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == workspace_id,
        )
    )


def require_workspace_access(
    db: Session,
    user: User,
    workspace_id: str | None,
    min_role: Role = Role.VIEWER,
) -> None:
    """Raise 403 unless ``user`` may act in ``workspace_id`` at ``min_role`` level.

    The default workspace is open to every authenticated user; workspace
    creators and superusers always have owner-level access.
    """
    if workspace_id is None or workspace_id == DEFAULT_WORKSPACE_ID:
        return
    if is_superuser(db, user):
        return
    ws = db.get(Workspace, workspace_id)
    if ws is not None and ws.created_by == user.id:
        return
    membership = get_membership(db, user, workspace_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )
    if _role_level(membership.role) < ROLE_ORDER.get(min_role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least {min_role.value} role",
        )


def require_project_access(
    db: Session,
    user: User,
    project_id: str,
    min_role: Role = Role.VIEWER,
) -> Project:
    """Load a project, enforcing workspace access. 404 if missing, 403 if denied."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    require_workspace_access(db, user, project.workspace_id, min_role)
    return project


def require_job_access(db: Session, user: User, job: object) -> None:
    """Enforce access to a Job row via the project referenced in its payload.

    Jobs created before this check (or maintenance jobs) may not reference a
    project; those are visible to any authenticated user.
    """
    import json

    project_id: str | None = None
    payload_json = getattr(job, "payload_json", None)
    if payload_json:
        try:
            payload = json.loads(payload_json)
            project_id = payload.get("projectId") or payload.get("project_id")
        except (ValueError, TypeError):
            project_id = None
    if not project_id:
        return
    project = db.get(Project, project_id)
    if project is None:
        return
    require_workspace_access(db, user, project.workspace_id)


def require_dataset_access(
    db: Session,
    user: User,
    dataset_id: str,
    min_role: Role = Role.VIEWER,
) -> Dataset:
    """Load a dataset, enforcing access on its owning project's workspace."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    require_project_access(db, user, dataset.project_id, min_role)
    return dataset
