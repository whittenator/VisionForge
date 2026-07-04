from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.dataset_version import DatasetVersion
from app.models.user import User
from app.models.workspace import Role
from app.schemas.split import SplitConfig, SplitSummary
from app.services import authz, split_service
from app.services.annotation_service import get_asset_annotations
from app.services.asset_service import (
    confirm_upload,
    get_asset,
    get_dataset_metrics,
    get_dataset_stats,
    list_assets,
)
from app.services.similarity_service import find_duplicates, find_similar

router = APIRouter(prefix="/api", tags=["assets"])


class ConfirmUploadRequest(BaseModel):
    dataset_id: str
    version_id: str
    storage_key: str
    filename: str
    content_type: str = "image/jpeg"
    width: int | None = None
    height: int | None = None


def _require_version_dataset_access(
    db: Session,
    user: User,
    dataset_id: str,
    version_id: str,
    min_role: Role,
) -> None:
    """Enforce access against the version's *actual* owning dataset when it
    resolves, falling back to the dataset id from the path/body otherwise."""
    version = db.get(DatasetVersion, version_id)
    owner = version.dataset_id if version is not None else dataset_id
    authz.require_dataset_access(db, user, owner, min_role)


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
    authz.require_dataset_access(db, current_user, asset.dataset_id, Role.VIEWER)
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
    asset = get_asset(db, asset_id)
    if asset is not None:
        authz.require_dataset_access(db, current_user, asset.dataset_id, Role.VIEWER)
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
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
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
    _require_version_dataset_access(db, current_user, dataset_id, version_id, Role.VIEWER)
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
    _require_version_dataset_access(db, current_user, dataset_id, version_id, Role.DEVELOPER)
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
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    return get_dataset_stats(db, dataset_id, version_id=version_id)


@router.get("/datasets/{dataset_id}/metrics")
def dataset_metrics(
    dataset_id: str = Path(...),
    version_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detailed dataset health metrics for the metrics dashboard."""
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
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
    authz.require_dataset_access(db, current_user, asset.dataset_id, Role.VIEWER)

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


@router.get("/assets/{asset_id}/similar")
def get_similar_assets(
    asset_id: str = Path(...),
    k: int = Query(20, ge=1, le=100),
    dataset_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the nearest neighbours of an asset by embedding cosine distance."""
    from app.models.asset import Asset

    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    authz.require_dataset_access(db, current_user, asset.dataset_id, Role.VIEWER)

    scope = dataset_id or asset.dataset_id
    if dataset_id and dataset_id != asset.dataset_id:
        authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)

    neighbors = find_similar(db, asset_id, k=k, dataset_id=scope)
    return {
        "query_asset_id": asset_id,
        "items": [
            {
                "id": neighbor.id,
                "uri": neighbor.uri,
                "download_url": _presign_download(neighbor.uri),
                "distance": distance,
                "label_status": neighbor.label_status,
            }
            for neighbor, distance in neighbors
        ],
    }


@router.get("/datasets/{dataset_id}/duplicates")
def get_dataset_duplicates(
    dataset_id: str = Path(...),
    threshold: float = Query(0.05, ge=0.0, le=2.0),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return near-duplicate asset pairs within a dataset."""
    authz.require_dataset_access(db, current_user, dataset_id, Role.VIEWER)
    result = find_duplicates(db, dataset_id, threshold=threshold, max_pairs=limit)

    def _serialize(asset) -> dict:
        return {
            "id": asset.id,
            "uri": asset.uri,
            "download_url": _presign_download(asset.uri),
        }

    return {
        "pairs": [
            {
                "distance": pair["distance"],
                "asset_a": _serialize(pair["asset_a"]),
                "asset_b": _serialize(pair["asset_b"]),
            }
            for pair in result["pairs"]
        ],
        "total": result["total"],
        "computed": result["computed"],
        "truncated": result["truncated"],
    }


@router.post("/datasets/{dataset_id}/embeddings", status_code=202)
def queue_dataset_embeddings(
    dataset_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dispatch the Celery task that (re)generates embeddings for a dataset.

    Targets the newest dataset version so the UI can build embeddings before
    running duplicate detection or similarity search.
    """
    from sqlalchemy import select

    from app.jobs.celery_app import celery_app
    from app.services.jobs_service import create_job, update_job_status

    authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)

    version = db.scalars(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version.desc())
    ).first()
    if version is None:
        raise HTTPException(status_code=400, detail="dataset has no versions")

    job = create_job(db, "embeddings", {"datasetVersionId": version.id})
    try:
        celery_app.send_task(
            "app.jobs.tasks.embeddings.generate_embeddings",
            args=[{"jobId": job.id, "datasetVersionId": version.id}],
        )
    except Exception as exc:
        try:
            update_job_status(db, job.id, status="failed", progress=0.0)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=f"failed to dispatch task: {exc}") from exc

    return {"jobId": job.id, "status": "queued", "datasetVersionId": version.id}


@router.post("/ingest/confirm", status_code=201)
def confirm_asset_upload(
    body: ConfirmUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_dataset_access(db, current_user, body.dataset_id, Role.DEVELOPER)
    version = db.get(DatasetVersion, body.version_id)
    if version is not None and version.dataset_id != body.dataset_id:
        authz.require_dataset_access(db, current_user, version.dataset_id, Role.DEVELOPER)
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
