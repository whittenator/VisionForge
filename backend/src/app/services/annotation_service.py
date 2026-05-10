from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.annotation import ANNOTATION_TYPES, REVIEW_STATUSES, Annotation
from app.models.asset import Asset


class AnnotationError(Exception):
    pass


class VersionConflictError(AnnotationError):
    """Raised when a client's version doesn't match the server's."""


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
    commit: bool = True,
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
    if commit:
        db.commit()
        db.refresh(ann)
    else:
        db.flush()
    return ann


def update_annotation(
    db: Session,
    annotation_id: str,
    *,
    geometry: dict | None = None,
    class_name: str | None = None,
    expected_version: int | None = None,
    commit: bool = True,
) -> Annotation | None:
    ann = db.get(Annotation, annotation_id)
    if not ann:
        return None
    if expected_version is not None and ann.version != expected_version:
        raise VersionConflictError(
            f"annotation version mismatch: have {ann.version}, expected {expected_version}"
        )

    geometry_changing = geometry is not None
    class_changing = class_name is not None and class_name != ann.class_name
    if not geometry_changing and not class_changing:
        return ann

    if geometry_changing:
        _validate_geometry(ann.type, geometry)

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
    # An edit invalidates a prior review.
    if ann.review_status != "unreviewed":
        ann.review_status = "unreviewed"
        ann.reviewer_id = None
        ann.reviewed_at = None
    db.add(ann)
    if commit:
        db.commit()
        db.refresh(ann)
    else:
        db.flush()
    return ann


def delete_annotation(db: Session, annotation_id: str, *, commit: bool = True) -> bool:
    ann = db.get(Annotation, annotation_id)
    if not ann:
        return False
    db.delete(ann)
    if commit:
        db.commit()
    else:
        db.flush()
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


def set_review(
    db: Session,
    annotation_id: str,
    *,
    review_status: str,
    reviewer_id: str,
    notes: str | None = None,
) -> Annotation | None:
    """Approve / reject / reset an annotation."""
    if review_status not in REVIEW_STATUSES:
        raise AnnotationError(
            f"review_status must be one of {REVIEW_STATUSES}, got {review_status!r}"
        )
    ann = db.get(Annotation, annotation_id)
    if not ann:
        return None
    ann.review_status = review_status
    if review_status == "unreviewed":
        ann.reviewer_id = None
        ann.reviewed_at = None
        ann.review_notes = None
    else:
        ann.reviewer_id = reviewer_id
        ann.reviewed_at = datetime.now(timezone.utc)
        ann.review_notes = notes
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


def list_review_queue(
    db: Session,
    *,
    dataset_id: str,
    version_id: str | None = None,
    review_status: str | None = None,
    flagged: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """List annotations + parent-asset metadata for a review queue."""
    base = (
        select(Annotation, Asset)
        .join(Asset, Asset.id == Annotation.asset_id)
        .where(Asset.dataset_id == dataset_id)
    )
    if version_id:
        base = base.where(Asset.version_id == version_id)
    if review_status:
        if review_status not in REVIEW_STATUSES:
            raise AnnotationError(
                f"review_status must be one of {REVIEW_STATUSES}, got {review_status!r}"
            )
        base = base.where(Annotation.review_status == review_status)
    if flagged is not None:
        base = base.where(Annotation.flagged == flagged)

    count_q = (
        select(func.count(Annotation.id))
        .join(Asset, Asset.id == Annotation.asset_id)
        .where(Asset.dataset_id == dataset_id)
    )
    if version_id:
        count_q = count_q.where(Asset.version_id == version_id)
    if review_status:
        count_q = count_q.where(Annotation.review_status == review_status)
    if flagged is not None:
        count_q = count_q.where(Annotation.flagged == flagged)
    total = db.scalar(count_q) or 0

    offset = (page - 1) * page_size
    rows = list(
        db.execute(
            base.order_by(Annotation.created_at.desc()).offset(offset).limit(page_size)
        ).all()
    )
    items = []
    for ann, asset in rows:
        items.append(
            {
                "annotation": _ann_dict(ann),
                "asset": {
                    "id": asset.id,
                    "uri": asset.uri,
                    "width": asset.width,
                    "height": asset.height,
                    "label_status": asset.label_status,
                },
            }
        )
    return items, total


def review_summary(
    db: Session, *, dataset_id: str, version_id: str | None = None
) -> dict[str, int]:
    """Counts of annotations by review status (and flagged) for a dataset/version."""
    base = (
        select(Annotation.review_status, Annotation.flagged, func.count(Annotation.id))
        .join(Asset, Asset.id == Annotation.asset_id)
        .where(Asset.dataset_id == dataset_id)
        .group_by(Annotation.review_status, Annotation.flagged)
    )
    if version_id:
        base = base.where(Asset.version_id == version_id)
    counts = {s: 0 for s in REVIEW_STATUSES}
    flagged_count = 0
    total = 0
    for status, flagged, n in db.execute(base).all():
        if status in counts:
            counts[status] += int(n)
        if flagged:
            flagged_count += int(n)
        total += int(n)
    return {**counts, "flagged": flagged_count, "total": total}


def bulk_save(
    db: Session,
    *,
    author_id: str,
    creates: list[dict[str, Any]] | None = None,
    updates: list[dict[str, Any]] | None = None,
    deletes: list[str] | None = None,
) -> dict[str, Any]:
    """Apply many annotation mutations in one round-trip.

    Each entry is wrapped in a SAVEPOINT (``db.begin_nested()``) so a single
    failed row rolls back just that row, leaving the rest of the batch
    intact. The whole batch is then committed in **one** outer transaction
    — no more O(n) commits like the original implementation. The response
    surfaces per-entry status so the client can show 409s on the rows that
    conflicted.
    """
    creates = creates or []
    updates = updates or []
    deletes = deletes or []

    created_results: list[dict[str, Any]] = []
    updated_results: list[dict[str, Any]] = []
    deleted_results: list[dict[str, Any]] = []

    affected_assets: set[str] = set()

    # If the session has no active transaction we need to start one before
    # opening savepoints. SQLAlchemy 2.0 autoflush sessions don't carry an
    # implicit transaction across commits.
    if not db.in_transaction():
        db.begin()

    for c in creates:
        client_id = c.get("client_id")
        sp = db.begin_nested()
        try:
            ann = create_annotation(
                db,
                asset_id=c["asset_id"],
                author_id=author_id,
                type=c["type"],
                geometry=c["geometry"],
                class_name=c.get("class_name"),
                commit=False,
            )
            sp.commit()
            affected_assets.add(c["asset_id"])
            created_results.append(
                {
                    "client_id": client_id,
                    "status": "ok",
                    "annotation": _ann_dict(ann),
                }
            )
        except AnnotationError as exc:
            sp.rollback()
            created_results.append({"client_id": client_id, "status": "error", "error": str(exc)})

    for u in updates:
        ann_id = u.get("id")
        if not ann_id:
            updated_results.append({"id": None, "status": "error", "error": "missing id"})
            continue
        sp = db.begin_nested()
        try:
            ann = update_annotation(
                db,
                ann_id,
                geometry=u.get("geometry"),
                class_name=u.get("class_name"),
                expected_version=u.get("expected_version"),
                commit=False,
            )
            if not ann:
                sp.rollback()
                updated_results.append({"id": ann_id, "status": "not_found"})
                continue
            sp.commit()
            affected_assets.add(ann.asset_id)
            updated_results.append({"id": ann_id, "status": "ok", "annotation": _ann_dict(ann)})
        except VersionConflictError as exc:
            sp.rollback()
            updated_results.append({"id": ann_id, "status": "conflict", "error": str(exc)})
        except AnnotationError as exc:
            sp.rollback()
            updated_results.append({"id": ann_id, "status": "error", "error": str(exc)})

    for ann_id in deletes:
        ann = db.get(Annotation, ann_id)
        if ann is not None:
            affected_assets.add(ann.asset_id)
        sp = db.begin_nested()
        try:
            ok = delete_annotation(db, ann_id, commit=False)
            sp.commit()
        except Exception:
            sp.rollback()
            ok = False
        deleted_results.append({"id": ann_id, "status": "ok" if ok else "not_found"})

    # Best-effort: any asset that still has at least one annotation flips to
    # "in_progress" if it was "unlabeled". We don't auto-promote to "labeled"
    # — that's an explicit action via mark-labeled.
    for asset_id in affected_assets:
        asset = db.get(Asset, asset_id)
        if asset and asset.label_status in ("unlabeled", "unlabelled"):
            remaining = db.scalar(
                select(func.count(Annotation.id)).where(Annotation.asset_id == asset_id)
            )
            if remaining and int(remaining) > 0:
                asset.label_status = "in_progress"
                db.add(asset)

    # Single commit for the whole batch.
    db.commit()

    return {
        "created": created_results,
        "updated": updated_results,
        "deleted": deleted_results,
    }


def _ann_dict(ann: Annotation) -> dict[str, Any]:
    return {
        "id": ann.id,
        "asset_id": ann.asset_id,
        "type": ann.type,
        "geometry": (json.loads(ann.geometry) if isinstance(ann.geometry, str) else ann.geometry),
        "class_name": ann.class_name,
        "author_id": ann.author_id,
        "version": ann.version,
        "review_status": ann.review_status,
        "reviewer_id": ann.reviewer_id,
        "reviewed_at": ann.reviewed_at.isoformat() if ann.reviewed_at else None,
        "review_notes": ann.review_notes,
        "flagged": bool(ann.flagged),
        "flag_reason": ann.flag_reason,
        "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
        "created_at": ann.created_at.isoformat() if ann.created_at else None,
    }


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
            # Class label travels on the row, not the geometry.
            pass
    else:  # pragma: no cover - guarded above
        raise AnnotationError(f"unsupported type {atype}")
