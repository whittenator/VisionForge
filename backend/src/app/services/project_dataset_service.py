from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.project import Project


def create_project(db: Session, name: str, description: str | None) -> Project:
    # For now, use a dummy workspace_id. In a real implementation, 
    # we'd get this from the authenticated user's workspace
    dummy_workspace_id = "00000000-0000-0000-0000-000000000000"
    slug = name.lower().replace(" ", "-")
    p = Project(workspace_id=dummy_workspace_id, name=name, slug=slug, description=description)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_dataset(db: Session, project_id: str, name: str, description: str | None = None) -> tuple[Dataset, DatasetVersion]:
    """Create a dataset and its initial version"""
    d = Dataset(project_id=project_id, name=name, description=description)
    db.add(d)
    db.flush()  # Get the dataset ID without committing
    
    # Create initial version
    v = DatasetVersion(dataset_id=d.id, version=1)
    db.add(v)
    db.commit()
    db.refresh(d)
    db.refresh(v)
    return d, v
