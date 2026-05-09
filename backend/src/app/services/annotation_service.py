from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.annotation import ANNOTATION_TYPES, Annotation
from app.models.asset import Asset


class AnnotationError(Exception):
    pass


class VersionConflictError(AnnotationError):
    """Raised when a client's version doesn't match the server's."""


def get_asset_annotations(db: Session, asset_id: str) -> list[Annotation]:
    return list(
        db.scalars(select(Annotation).where(Annotation.asset_id == asset_id)).all()
    )


def create_annotation(
    db: Session,
    *,
    asset_id: str,
    author_id: str,
    type: str,
    geometry: dict,
    class_name: str | None,
) -> Annotation:
    if type not in ANNOTATION_TYPES:
        raise AnnotationError(
            f"unsupported annotation type '{type}', expected one of {ANNOTATION_TYPES}"
        )
    _validate_geometry(type, geometry)
    ann = Annotation(
        asset_id=asset_id,
        author_id=author_id,
        type=type,
        geometry=json.dumps(geometry),
        class_name=class_name,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(ann)
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
    expected_version: int | None = None,
) -> Annotation | None:
    ann = db.get(Annotation, annotation_id)
    if not ann:
        return None
    if expected_version is not None and ann.version != expected_version:
        raise VersionConflictError(
            f"annotation version mismatch: have {ann.version}, expected {expected_version}"
        )

    # Determine whether anything actually changes. An update with neither
    # field is a no-op — return the current row without bumping the version
    # (which would create needless optimistic-lock conflicts).
    geometry_changing = geometry is not None
    class_changing = class_name is not None and class_name != ann.class_name
    if not geometry_changing and not class_changing:
        return ann

    if geometry_changing:
        _validate_geometry(ann.type, geometry)

    # Snapshot the previous state into history whenever either the geometry
    # OR the class label changes, so the audit trail is faithful.
    history: list[dict] = []
    if ann.history:
        try:
            history = json.loads(ann.history) or []
        except Exception:
            history = []
    history.append(
        {
            "version": ann.version,
            "geometry": ann.geometry,
            "class_name": ann.class_name,
            "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
        }
    )
    ann.history = json.dumps(history[-20:])

    if geometry_changing:
        ann.geometry = json.dumps(geometry)
    if class_changing:
        ann.class_name = class_name
    ann.version = (ann.version or 1) + 1
    ann.updated_at = datetime.now(timezone.utc)
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


def get_history(db: Session, annotation_id: str) -> list[dict]:
    ann = db.get(Annotation, annotation_id)
    if not ann or not ann.history:
        return []
    try:
        return json.loads(ann.history) or []
    except Exception:
        return []


def mark_asset_labeled(db: Session, asset_id: str) -> None:
    asset = db.get(Asset, asset_id)
    if asset:
        asset.label_status = "labeled"
        db.add(asset)
        db.commit()


def _validate_geometry(atype: str, geometry: dict) -> None:
    if atype == "box":
        for k in ("x", "y", "w", "h"):
            if k not in geometry:
                raise AnnotationError(f"box geometry missing '{k}'")
        if geometry.get("w", 0) <= 0 or geometry.get("h", 0) <= 0:
            raise AnnotationError("box geometry must have positive width/height")
    elif atype == "polygon":
        points = geometry.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise AnnotationError("polygon requires at least 3 points")
        for p in points:
            if "x" not in p or "y" not in p:
                raise AnnotationError("polygon point missing 'x' or 'y'")
    elif atype == "keypoint":
        points = geometry.get("points")
        if not isinstance(points, list) or len(points) < 1:
            raise AnnotationError("keypoint requires at least 1 point")
        for p in points:
            if "x" not in p or "y" not in p:
                raise AnnotationError("keypoint point missing 'x' or 'y'")
    elif atype == "classification":
        if not geometry.get("class") and not geometry.get("class_name"):
            # Allow empty class field — class_name on the row carries the label.
            pass
    else:  # pragma: no cover - guarded above
        raise AnnotationError(f"unsupported type {atype}")
