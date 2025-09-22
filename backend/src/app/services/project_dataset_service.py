from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.project import Project


def create_project(db: Session, name: str, description: str | None) -> Project:
    p = Project(name=name, description=description)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_dataset(db: Session, project_id: str, name: str, media_type: str) -> tuple[Dataset, DatasetVersion]:
    d = Dataset(project_id=project_id, name=name, media_type=media_type)
    db.add(d)
    # Create initial version automatically
    v = DatasetVersion(dataset=d)
    db.add(v)
    db.commit()
    db.refresh(d)
    db.refresh(v)
    return d, v
