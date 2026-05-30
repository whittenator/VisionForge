from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.split import SplitConfig, SplitSummary
from app.services import split_service
from app.services.annotation_service import get_asset_annotations
from app.services.asset_service import (
    confirm_upload,
    get_asset,
    get_dataset_metrics,
    get_dataset_stats,
    list_assets,
)

router = APIRouter(prefix="/api", tags=["assets"])


class ConfirmUploadRequest(BaseModel):
    dataset_id: str
    version_id: str
    storage_key: str
    filename: str
    content_type: str = "image/jpeg"
    width: int | None = None
    height: int | None = None


def _presign_download(uri: str) -> str:
    """Attempt to generate a presigned download URL; fall back to raw URI."""
    try:
        from app.services import storage

        client = storage.get_minio_client()
        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        from datetime import timedelta

        return client.presigned_get_object(bucket, uri, expires=timedelta(seconds=3600))
    except Exception:
        return uri


@router.get("/assets/{asset_id}")
def get(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    download_url = _presign_download(asset.uri)
    meta: dict = {}
    if asset.meta_data:
        try:
            meta = json.loads(asset.meta_data)
        except Exception:
            pass
    return {
        "id": asset.id,
        "dataset_id": asset.dataset_id,
        "version_id": asset.version_id,
        "uri": asset.uri,
        "download_url": download_url,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "label_status": asset.label_status,
        "meta": meta,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.get("/assets/{asset_id}/annotations")
def get_annotations(
    asset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    anns = get_asset_annotations(db, asset_id)
    return [
        {
            "id": a.id,
            "asset_id": a.asset_id,
            "type": a.type,
            "geometry": json.loads(a.geometry) if isinstance(a.geometry, str) else a.geometry,
            "class_name": a.class_name,
            "author_id": a.author_id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in anns
    ]


@router.get("/datasets/{dataset_id}/assets")
def list_dataset_assets(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    label_status: str | None = Query(None),
    split: str | None = Query(None, description="Filter by train/val/test split"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assets, total = list_assets(
        db,
        dataset_id,
        version_id=version_id,
        label_status=label_status,
        split=split,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": a.id,
                "uri": a.uri,
                "download_url": _presign_download(a.uri),
                "mime_type": a.mime_type,
                "width": a.width,
                "height": a.height,
                "label_status": a.label_status,
                "split": split_service.asset_split(a),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/datasets/{dataset_id}/versions/{version_id}/split", response_model=SplitSummary)
def get_version_split(
    dataset_id: str = Path(...),
    version_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return persisted train/val/test counts and per-class breakdown for a version."""
    return split_service.get_split_summary(db, version_id)


@router.post("/datasets/{dataset_id}/versions/{version_id}/split", response_model=SplitSummary)
def assign_version_split(
    body: SplitConfig,
    dataset_id: str = Path(...),
    version_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically (re)assign and persist the split for every asset in a version."""
    try:
        return split_service.assign_splits(
            db,
            version_id,
            train=body.train,
            val=body.val,
            test=body.test,
            seed=body.seed,
            stratify=body.stratify,
        )
    except split_service.SplitConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}/stats")
def dataset_stats(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dataset_stats(db, dataset_id, version_id=version_id)


@router.get("/datasets/{dataset_id}/metrics")
def dataset_metrics(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detailed dataset health metrics for the metrics dashboard."""
    return get_dataset_metrics(db, dataset_id, version_id=version_id)


@router.get("/assets/{asset_id}/neighbors")
def get_asset_neighbors(
    asset_id: str = Path(...),
    label_status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return previous/next asset ids in the same dataset version.

    Ordering is `(created_at, id)` ascending. Uses two indexed range queries
    plus a count, so it stays O(log n) per call instead of materialising the
    whole asset list.
    """
    from sqlalchemy import and_, asc, desc, func, or_, select

    from app.models.asset import Asset

    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    base_filters = [Asset.dataset_id == asset.dataset_id]
    if asset.version_id:
        base_filters.append(Asset.version_id == asset.version_id)
    if label_status:
        base_filters.append(Asset.label_status == label_status)

    # The ordering key is (created_at, id). "before" rows are strictly less
    # than the cursor, "after" rows are strictly greater.
    cursor_created = asset.created_at
    cursor_id = asset.id

    if cursor_created is None:
        # No created_at to compare; fall back to id-only ordering.
        before_filter = Asset.id < cursor_id
        after_filter = Asset.id > cursor_id
        order_before = (desc(Asset.id),)
        order_after = (asc(Asset.id),)
    else:
        before_filter = or_(
            Asset.created_at < cursor_created,
            and_(Asset.created_at == cursor_created, Asset.id < cursor_id),
        )
        after_filter = or_(
            Asset.created_at > cursor_created,
            and_(Asset.created_at == cursor_created, Asset.id > cursor_id),
        )
        order_before = (desc(Asset.created_at), desc(Asset.id))
        order_after = (asc(Asset.created_at), asc(Asset.id))

    prev_id = db.scalar(
        select(Asset.id).where(*base_filters, before_filter).order_by(*order_before).limit(1)
    )
    next_id = db.scalar(
        select(Asset.id).where(*base_filters, after_filter).order_by(*order_after).limit(1)
    )
    total = (
        db.scalar(
            select(func.count()).select_from(select(Asset.id).where(*base_filters).subquery())
        )
        or 0
    )
    index_before = (
        db.scalar(
            select(func.count()).select_from(
                select(Asset.id).where(*base_filters, before_filter).subquery()
            )
        )
        or 0
    )

    return {
        "prev": prev_id,
        "next": next_id,
        "index": index_before,
        "total": total,
    }


@router.post("/ingest/confirm", status_code=201)
def confirm_asset_upload(
    body: ConfirmUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = confirm_upload(
        db,
        dataset_id=body.dataset_id,
        version_id=body.version_id,
        storage_key=body.storage_key,
        filename=body.filename,
        content_type=body.content_type,
        width=body.width,
        height=body.height,
    )
    return {"id": asset.id, "dataset_id": asset.dataset_id, "label_status": asset.label_status}
