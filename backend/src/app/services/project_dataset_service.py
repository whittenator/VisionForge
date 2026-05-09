from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.project import Project

VALID_TASK_TYPES = ("detect", "classify")


def create_project(
    db: Session,
    name: str,
    description: str | None,
    *,
    task_type: str | None = None,
    workspace_id: str | None = None,
) -> Project:
    if task_type is not None and task_type not in VALID_TASK_TYPES:
        raise ValueError(f"task_type must be one of {VALID_TASK_TYPES}, got {task_type!r}")
    workspace_id = workspace_id or "00000000-0000-0000-0000-000000000000"
    slug = name.lower().replace(" ", "-")
    p = Project(
        workspace_id=workspace_id,
        name=name,
        slug=slug,
        description=description,
        task_type=task_type,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_dataset(
    db: Session,
    project_id: str,
    name: str,
    description: str | None = None,
    *,
    task_type: str | None = None,
) -> tuple[Dataset, DatasetVersion]:
    """Create a dataset and its initial version.

    If ``task_type`` is omitted, the dataset inherits its parent project's
    task_type (which is itself optional for legacy projects).
    """
    if task_type is not None and task_type not in VALID_TASK_TYPES:
        raise ValueError(f"task_type must be one of {VALID_TASK_TYPES}, got {task_type!r}")
    if task_type is None:
        project = db.get(Project, project_id)
        task_type = project.task_type if project else None

    d = Dataset(
        project_id=project_id,
        name=name,
        description=description,
        task_type=task_type,
    )
    db.add(d)
    db.flush()  # Get the dataset ID without committing

    # Create initial version
    v = DatasetVersion(dataset_id=d.id, version=1)
    db.add(v)
    db.commit()
    db.refresh(d)
    db.refresh(v)
    return d, v
