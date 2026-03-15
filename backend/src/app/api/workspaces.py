from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.models.workspace import Membership, Role, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str
    region: str = "US"


class InviteMember(BaseModel):
    email: str
    role: str = "annotator"


@router.get("")
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = list(
        db.scalars(select(Membership).where(Membership.user_id == current_user.id)).all()
    )
    workspace_ids = [m.workspace_id for m in memberships]
    workspaces_by_membership = (
        list(db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids))).all())
        if workspace_ids
        else []
    )
    # Also include workspaces created by user
    own = list(
        db.scalars(select(Workspace).where(Workspace.created_by == current_user.id)).all()
    )
    all_ws = {w.id: w for w in workspaces_by_membership + own}
    return [
        {
            "id": w.id,
            "name": w.name,
            "region": w.region,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in all_ws.values()
    ]


@router.post("", status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ws = Workspace(name=body.name, region=body.region, created_by=current_user.id)
    db.add(ws)
    db.flush()
    # Add creator as owner
    m = Membership(
        user_id=current_user.id,
        workspace_id=ws.id,
        role=Role.OWNER,
        invited_by=current_user.id,
    )
    db.add(m)
    db.commit()
    db.refresh(ws)
    return {"id": ws.id, "name": ws.name, "region": ws.region}


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ws = db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "id": ws.id,
        "name": ws.name,
        "region": ws.region,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
    }


@router.get("/{workspace_id}/members")
def list_members(
    workspace_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    members = list(
        db.scalars(select(Membership).where(Membership.workspace_id == workspace_id)).all()
    )
    result = []
    for m in members:
        u = db.get(User, m.user_id)
        result.append(
            {
                "user_id": m.user_id,
                "email": u.email if u else None,
                "name": u.name if u else None,
                "role": m.role,
            }
        )
    return result


@router.post("/{workspace_id}/members", status_code=201)
def invite_member(
    body: InviteMember,
    workspace_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ws = db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    # Look up user by email
    invited_user = db.scalars(
        select(User).where(User.email == body.email)
    ).first()
    if not invited_user:
        raise HTTPException(status_code=404, detail="User not found")
    # Check if already a member
    existing = db.scalars(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == invited_user.id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")
    role_value = body.role if body.role in [r.value for r in Role] else Role.ANNOTATOR.value
    m = Membership(
        user_id=invited_user.id,
        workspace_id=workspace_id,
        role=role_value,
        invited_by=current_user.id,
    )
    db.add(m)
    db.commit()
    return {"user_id": invited_user.id, "workspace_id": workspace_id, "role": role_value}
