from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.project import Project


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).order_by(Project.created_at.desc()).all()


def create_project(db: Session, name: str, description: str | None = None) -> Project:
    proj = Project(name=name, description=description or "")
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def add_membership(db: Session, project_id: int, user_id: int, role: str = "member") -> Membership:
    membership = Membership(project_id=project_id, user_id=user_id, role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership
