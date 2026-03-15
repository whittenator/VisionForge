from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.asset import Asset
from app.models.dataset_version import DatasetVersion


def get_asset(db: Session, asset_id: str) -> Asset | None:
    return db.get(Asset, asset_id)


def list_assets(
    db: Session,
    dataset_id: str,
    *,
    version_id: str | None = None,
    label_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Asset], int]:
    q = select(Asset).where(Asset.dataset_id == dataset_id)
    if version_id:
        q = q.where(Asset.version_id == version_id)
    if label_status:
        q = q.where(Asset.label_status == label_status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    assets = list(db.scalars(q.offset(offset).limit(limit)).all())
    return assets, total or 0


def confirm_upload(
    db: Session,
    *,
    dataset_id: str,
    version_id: str,
    storage_key: str,
    filename: str,
    content_type: str,
    width: int | None = None,
    height: int | None = None,
) -> Asset:
    """Register an asset after successful upload to MinIO."""
    ver = db.get(DatasetVersion, version_id)
    if ver and ver.locked:
        raise HTTPException(status_code=400, detail="Cannot add assets to a locked dataset version")
    asset = Asset(
        dataset_id=dataset_id,
        version_id=version_id,
        uri=storage_key,
        mime_type=content_type or "application/octet-stream",
        width=width,
        height=height,
        label_status="unlabeled",
        meta_data=json.dumps({"filename": filename}),
    )
    db.add(asset)
    # Update asset_count on the version
    version = db.get(DatasetVersion, version_id)
    if version:
        version.asset_count = (version.asset_count or 0) + 1
        db.add(version)
    db.commit()
    db.refresh(asset)
    return asset


def get_dataset_stats(db: Session, dataset_id: str, version_id: str | None = None) -> dict:
    """Return class distribution, annotation coverage, label status breakdown."""
    q = select(Asset).where(Asset.dataset_id == dataset_id)
    if version_id:
        q = q.where(Asset.version_id == version_id)
    assets = list(db.scalars(q).all())
    asset_ids = [a.id for a in assets]

    # Label status distribution
    status_counts: dict[str, int] = {}
    for a in assets:
        status_counts[a.label_status] = status_counts.get(a.label_status, 0) + 1

    # Class distribution from annotations
    class_counts: dict[str, int] = {}
    if asset_ids:
        anns = list(
            db.scalars(select(Annotation).where(Annotation.asset_id.in_(asset_ids))).all()
        )
        for ann in anns:
            cls = ann.class_name or "unlabeled"
            class_counts[cls] = class_counts.get(cls, 0) + 1

    total = len(assets)
    labeled = status_counts.get("labeled", 0) + status_counts.get("prelabeled", 0)

    return {
        "total_assets": total,
        "labeled": labeled,
        "unlabeled": status_counts.get("unlabeled", 0) + status_counts.get("unlabelled", 0),
        "in_progress": status_counts.get("in_progress", 0),
        "coverage_pct": round(labeled / total * 100, 1) if total > 0 else 0.0,
        "label_status_distribution": status_counts,
        "class_distribution": class_counts,
        "annotation_count": sum(class_counts.values()),
    }
