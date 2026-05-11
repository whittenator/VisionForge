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
    commit: bool = True,
) -> Project:
    """Create a Project row.

    By default the row is committed so single-call callers (e.g. ``POST
    /api/projects``) get a fully-persisted result. Multi-step callers like
    the wizard can pass ``commit=False`` and own the transaction boundary
    themselves so partial failures roll back cleanly.
    """
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
    if commit:
        db.commit()
        db.refresh(p)
    else:
        db.flush()
    return p


def create_dataset(
    db: Session,
    project_id: str,
    name: str,
    description: str | None = None,
    *,
    task_type: str | None = None,
    commit: bool = True,
) -> tuple[Dataset, DatasetVersion]:
    """Create a dataset and its initial version.

    If ``task_type`` is omitted, the dataset inherits its parent project's
    task_type (which is itself optional for legacy projects). Pass
    ``commit=False`` from inside a larger transaction (e.g. the wizard) so
    the caller can roll back cleanly on partial failure.
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
    if commit:
        db.commit()
        db.refresh(d)
        db.refresh(v)
    else:
        db.flush()
    return d, v
