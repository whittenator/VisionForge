from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion


def create_dataset(
    db: Session,
    project_id: int,
    name: str,
    description: str | None = None,
) -> tuple[Dataset, DatasetVersion]:
    ds = Dataset(project_id=project_id, name=name, description=description or "")
    db.add(ds)
    db.commit()
    db.refresh(ds)
    # create initial version
    ver = DatasetVersion(dataset_id=ds.id, version=1)
    db.add(ver)
    db.commit()
    db.refresh(ver)
    # set active version id if model supports
    try:
        ds.active_version_id = ver.id  # type: ignore[attr-defined]
        db.add(ds)
        db.commit()
        db.refresh(ds)
    except Exception:
        pass
    return ds, ver


def snapshot_version(db: Session, dataset_id: int) -> DatasetVersion:
    # compute next version number
    current_max = (
        db.query(func.max(DatasetVersion.version))
        .filter(DatasetVersion.dataset_id == dataset_id)
        .scalar()
        or 0
    )
    nxt = int(current_max) + 1
    ver = DatasetVersion(dataset_id=dataset_id, version=nxt)
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver
