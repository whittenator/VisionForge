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


def snapshot_version(db: Session, dataset_id: str, notes: str | None = None) -> DatasetVersion:
    """Create a new locked snapshot version for a dataset.

    The snapshot freezes the dataset's current working set, so its
    ``asset_count`` reflects the assets in the open (unlocked) version being
    captured — not every asset that has ever belonged to the dataset across
    all prior locked versions.
    """
    # Compute next version number
    versions = list(
        db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
        ).all()
    )
    next_version = (versions[0].version + 1) if versions else 1

    # Count assets in the working (unlocked) version being snapshotted. Fall
    # back to the whole dataset only when no open version exists (legacy data).
    open_version = next((v for v in versions if not v.locked), None)
    if open_version is not None:
        current_assets = (
            db.scalar(select(func.count(Asset.id)).where(Asset.version_id == open_version.id)) or 0
        )
    else:
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


def latest_open_version(db: Session, dataset_id: str) -> DatasetVersion | None:
    """Return the newest editable (unlocked) version, or None if all are locked.

    New imagery and annotations must land in an unlocked version; locked
    versions are immutable snapshots.
    """
    return db.scalars(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id, DatasetVersion.locked.is_(False))
        .order_by(DatasetVersion.version.desc())
    ).first()
