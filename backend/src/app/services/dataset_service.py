from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion


def create_dataset(
    db: Session,
    project_id: str,
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


def snapshot_version(
    db: Session, dataset_id: str, notes: str | None = None
) -> DatasetVersion:
    """Create a new locked snapshot version for a dataset."""
    # Compute next version number
    versions = list(
        db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
        ).all()
    )
    next_version = (versions[0].version + 1) if versions else 1

    # Get current asset count for this dataset
    current_assets = (
        db.scalar(select(func.count(Asset.id)).where(Asset.dataset_id == dataset_id)) or 0
    )

    ver = DatasetVersion(
        dataset_id=dataset_id,
        version=next_version,
        notes=notes,
        asset_count=current_assets,
        locked=True,
    )
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver
