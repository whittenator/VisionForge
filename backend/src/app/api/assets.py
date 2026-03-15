from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.services.annotation_service import get_asset_annotations
from app.services.asset_service import confirm_upload, get_asset, get_dataset_stats, list_assets

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
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": a.id,
                "uri": a.uri,
                "mime_type": a.mime_type,
                "width": a.width,
                "height": a.height,
                "label_status": a.label_status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/datasets/{dataset_id}/stats")
def dataset_stats(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dataset_stats(db, dataset_id, version_id=version_id)


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
