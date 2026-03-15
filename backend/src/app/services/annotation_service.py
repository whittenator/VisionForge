from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.asset import Asset


def get_asset_annotations(db: Session, asset_id: str) -> list[Annotation]:
    return list(db.scalars(select(Annotation).where(Annotation.asset_id == asset_id)).all())


def create_annotation(
    db: Session,
    *,
    asset_id: str,
    author_id: str,
    type: str,
    geometry: dict,
    class_name: str | None,
) -> Annotation:
    ann = Annotation(
        asset_id=asset_id,
        author_id=author_id,
        type=type,
        geometry=json.dumps(geometry),
        class_name=class_name,
    )
    db.add(ann)
    # Update asset label_status if was unlabeled
    asset = db.get(Asset, asset_id)
    if asset and asset.label_status in ("unlabeled", "unlabelled"):
        asset.label_status = "in_progress"
        db.add(asset)
    db.commit()
    db.refresh(ann)
    return ann


def update_annotation(
    db: Session,
    annotation_id: str,
    *,
    geometry: dict | None = None,
    class_name: str | None = None,
) -> Annotation | None:
    ann = db.get(Annotation, annotation_id)
    if not ann:
        return None
    if geometry is not None:
        old_history = json.loads(ann.history or "[]")
        old_history.append({"geometry": ann.geometry, "class_name": ann.class_name})
        ann.history = json.dumps(old_history[-10:])  # keep last 10 versions
        ann.geometry = json.dumps(geometry)
    if class_name is not None:
        ann.class_name = class_name
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


def delete_annotation(db: Session, annotation_id: str) -> bool:
    ann = db.get(Annotation, annotation_id)
    if not ann:
        return False
    db.delete(ann)
    db.commit()
    return True


def mark_asset_labeled(db: Session, asset_id: str) -> None:
    asset = db.get(Asset, asset_id)
    if asset:
        asset.label_status = "labeled"
        db.add(asset)
        db.commit()
