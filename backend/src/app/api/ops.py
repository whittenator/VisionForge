from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.dataset_version import DatasetVersion
from app.models.experiment import ExperimentRun
from app.models.user import User
from app.models.workspace import Role
from app.schemas.common import (
    Job,
    OnnxExportRequest,
    TrainRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services import authz, cluster_service
from app.services.ingest_service import get_presigned_upload
from app.services.onnx_service import OnnxDispatchError
from app.services.onnx_service import export_onnx as svc_export_onnx
from app.services.training_service import TaskTypeMismatch, launch_training

router = APIRouter(prefix="/api", tags=["ops"])


@router.post("/ingest/upload-url", response_model=UploadUrlResponse)
def get_upload_url(
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = db.get(DatasetVersion, payload.datasetVersionId)
    if version is not None:
        authz.require_dataset_access(db, current_user, version.dataset_id, Role.DEVELOPER)
    data = get_presigned_upload(payload.datasetVersionId, payload.filename, payload.contentType)
    # Derive the objectKey using the same path template as storage.presign_put_url
    object_key = f"datasets/{payload.datasetVersionId}/{payload.filename}"
    return UploadUrlResponse(
        url=data["url"],
        fields=data.get("fields", {}),
        objectKey=object_key,
    )


@router.post("/train", response_model=Job, status_code=202)
def train(
    payload: TrainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authz.require_project_access(db, current_user, payload.projectId, Role.DEVELOPER)
    version = db.get(DatasetVersion, payload.datasetVersionId)
    if version is not None:
        authz.require_dataset_access(db, current_user, version.dataset_id, Role.DEVELOPER)
    try:
        job = launch_training(
            db,
            payload.projectId,
            payload.datasetVersionId,
            payload.task,
            payload.params,
            name=payload.name,
            base_model=payload.baseModel,
            owner_id=current_user.id,
            cluster_id=payload.clusterId,
            framework=payload.framework,
        )
    except cluster_service.ClusterNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskTypeMismatch as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Job(**job)


@router.post("/export/onnx", response_model=Job, status_code=202)
def export_onnx(
    payload: OnnxExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.get(ExperimentRun, payload.experimentId)
    if run is not None:
        authz.require_project_access(db, current_user, run.project_id, Role.DEVELOPER)
    try:
        job = svc_export_onnx(
            db, payload.experimentId, payload.dynamicAxes, cluster_id=payload.clusterId
        )
    except cluster_service.ClusterNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OnnxDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Job(**job)


@router.get("/system/status")
def system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Live health for the home-page status panel.

    Probes API (always ok), DB, queue (Celery broker via ``ping`` inspect),
    and object storage (MinIO list-buckets). Each subsystem returns one of
    ``ok | degraded | down`` plus a short ``detail`` string.
    """
    components: dict[str, dict] = {}

    components["api"] = {"status": "ok", "detail": "responding"}

    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        components["database"] = {"status": "ok", "detail": "reachable"}
    except Exception as exc:  # pragma: no cover - depends on environment
        components["database"] = {"status": "down", "detail": str(exc)[:120]}

    components["queue"] = _probe_queue()
    components["storage"] = _probe_storage()

    statuses = {c["status"] for c in components.values()}
    overall = "down" if "down" in statuses else "degraded" if "degraded" in statuses else "ok"
    return {"status": overall, "components": components}


def _probe_queue() -> dict[str, str]:
    """Ping Celery; degrades gracefully if the broker isn't reachable."""
    try:
        from app.jobs.celery_app import celery_app

        replies = celery_app.control.ping(timeout=1.0) or []
    except Exception as exc:  # pragma: no cover - depends on environment
        return {"status": "down", "detail": f"ping failed: {exc}"[:120]}
    if replies:
        return {"status": "ok", "detail": f"{len(replies)} worker(s) online"}
    return {"status": "degraded", "detail": "no workers responding"}


def _probe_storage() -> dict[str, str]:
    """Verify the MinIO bucket exists. Treats a missing client as 'down'."""
    import os

    if os.getenv("MINIO_DISABLED", "false").lower() == "true":
        return {"status": "degraded", "detail": "MINIO_DISABLED=true"}
    try:
        from app.services import storage as storage_module

        client = storage_module.get_minio_client()
        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        if client.bucket_exists(bucket):
            return {"status": "ok", "detail": f"bucket {bucket} reachable"}
        return {"status": "degraded", "detail": f"bucket {bucket} missing"}
    except Exception as exc:  # pragma: no cover - depends on environment
        return {"status": "down", "detail": str(exc)[:120]}


@router.post(
    "/datasets/{dataset_id}/assets/{asset_id}/extract-frames",
    status_code=202,
)
def trigger_frame_extraction(
    dataset_id: str,
    asset_id: str,
    # Reject zero/negative intervals up-front: the worker uses this as a
    # divisor when computing the frame step, so a 0 or negative value would
    # blow up partway through. Cap at 600s so a typo can't queue a job that
    # extracts a single frame from a 10-minute video.
    fps_interval: float = Query(1.0, gt=0.0, le=600.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue a frame-extraction Celery task for a video asset."""
    authz.require_dataset_access(db, current_user, dataset_id, Role.DEVELOPER)
    from app.jobs.celery_app import celery_app
    from app.models.asset import Asset
    from app.services.jobs_service import create_job, update_job_status

    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.dataset_id != dataset_id:
        raise HTTPException(status_code=400, detail="asset does not belong to dataset")
    mime = (asset.mime_type or "").lower()
    if not mime.startswith("video/") and not asset.uri.lower().endswith(
        (".mp4", ".mov", ".avi", ".mkv", ".webm")
    ):
        raise HTTPException(status_code=400, detail="asset is not a video")

    payload = {
        "assetId": asset.id,
        "datasetVersionId": asset.version_id,
        "fpsInterval": float(fps_interval),
    }
    job = create_job(db, "frame_extraction", payload)
    payload["jobId"] = job.id
    try:
        celery_app.send_task("app.jobs.tasks.frame_extraction.extract_frames", args=[payload])
    except Exception as exc:
        # Don't leave the job stuck in `queued` if the broker is down.
        try:
            update_job_status(db, job.id, status="failed", progress=0.0)
        except Exception:
            pass
        raise HTTPException(
            status_code=503, detail=f"failed to dispatch frame extraction: {exc}"
        ) from exc
    return {"jobId": job.id, "status": "queued", "fpsInterval": fps_interval}
