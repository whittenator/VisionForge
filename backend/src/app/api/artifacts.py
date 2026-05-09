from __future__ import annotations

import base64
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.artifact import ModelArtifact
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.evaluation import Evaluation
from app.models.experiment import ExperimentRun
from app.models.user import User
from app.schemas.common import Job
from app.services import inference_service
from app.services.onnx_service import export_onnx as svc_export_onnx

router = APIRouter(prefix="/api", tags=["artifacts"])


def _artifact_dict(a: ModelArtifact) -> dict:
    return {
        "id": a.id,
        "projectId": a.project_id,
        "runId": a.run_id,
        "name": a.name,
        "version": a.version,
        "type": a.type,
        "format": a.format,
        "checksum": a.checksum,
        "sizeBytes": a.size_bytes,
        "storagePath": a.storage_path,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/artifacts/models")
def list_models(
    project_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(ModelArtifact)
    if project_id:
        base = base.where(ModelArtifact.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * page_size
    artifacts = list(
        db.scalars(
            base.order_by(ModelArtifact.created_at.desc()).offset(offset).limit(page_size)
        ).all()
    )
    return {
        "items": [_artifact_dict(a) for a in artifacts],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/artifacts/models/{model_id}")
def get_model(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "id": artifact.id,
        "projectId": artifact.project_id,
        "runId": artifact.run_id,
        "name": artifact.name,
        "version": artifact.version,
        "type": artifact.type,
        "format": artifact.format,
        "checksum": artifact.checksum,
        "sizeBytes": artifact.size_bytes,
        "storagePath": artifact.storage_path,
        "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
    }


class ExportRequest(BaseModel):
    cluster_id: str | None = None
    dynamic_axes: bool = True
    opset: int | None = None


@router.post("/artifacts/models/{model_id}/export", response_model=Job)
def export_model(
    model_id: str,
    body: ExportRequest = ExportRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import cluster_service

    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    # Use the artifact's run_id as experiment_id for ONNX export
    experiment_id = artifact.run_id or model_id
    try:
        job = svc_export_onnx(
            db,
            experiment_id,
            dynamic_axes=body.dynamic_axes,
            opset=body.opset,
            cluster_id=body.cluster_id,
        )
    except cluster_service.ClusterNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Job(**job)


@router.get("/artifacts/models/{model_id}/download")
def download_model(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a presigned download URL for the artifact's stored weights.

    Falls back to streaming from the local filesystem if the storage_path is
    a local path (e.g. tests, sqlite-only environments).
    """
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    if not artifact.storage_path:
        raise HTTPException(status_code=404, detail="artifact has no storage_path")

    # Local filesystem path → stream the file directly.
    if os.path.exists(artifact.storage_path):
        from fastapi.responses import FileResponse

        filename = os.path.basename(artifact.storage_path) or f"model-{model_id}"
        return FileResponse(
            artifact.storage_path,
            filename=filename,
            media_type="application/octet-stream",
        )

    # MinIO key → presigned GET.
    try:
        from app.services import storage as storage_module

        client = storage_module.get_minio_client()
        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        url = client.presigned_get_object(bucket, artifact.storage_path, expires=timedelta(hours=1))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"could not presign download: {exc}") from exc

    filename = os.path.basename(artifact.storage_path) or f"model-{model_id}"
    return {
        "url": url,
        "filename": filename,
        "size_bytes": artifact.size_bytes,
        "checksum": artifact.checksum,
        "expires_in": 3600,
    }


class PredictRequest(BaseModel):
    """JSON body for the base64 endpoint."""

    image_base64: str
    score_threshold: float = 0.25


def _predict_response(model_id: str, artifact, image_bytes: bytes, threshold: float) -> dict:
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty image")
    try:
        result = inference_service.predict(artifact, image_bytes, score_threshold=threshold)
    except inference_service.InferenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "model_id": model_id,
        "model_name": artifact.name,
        "model_version": artifact.version,
        "result": result,
    }


@router.post("/artifacts/models/{model_id}/predict")
async def predict_multipart(
    model_id: str,
    file: UploadFile = File(...),
    score_threshold: float = Form(0.25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run inference on the artifact via multipart upload (`file` field).

    Use this from browser file inputs / curl. For JSON callers, see
    `/predict-json` which accepts a base64-encoded image.
    """
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    image_bytes = await file.read()
    return _predict_response(model_id, artifact, image_bytes, score_threshold)


@router.post("/artifacts/models/{model_id}/predict-json")
def predict_json(
    model_id: str,
    body: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run inference on the artifact via a JSON body with a base64 image."""
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        image_bytes = base64.b64decode(body.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid base64") from exc
    return _predict_response(model_id, artifact, image_bytes, body.score_threshold)


@router.post("/artifacts/cache/clear")
def clear_inference_cache(
    current_user: User = Depends(get_current_user),
):
    """Drop all loaded models from the in-process inference cache."""
    inference_service._cache.clear()  # type: ignore[attr-defined]
    return {"ok": True}


@router.get("/artifacts/cache")
def get_inference_cache(
    current_user: User = Depends(get_current_user),
):
    return inference_service.cache_stats()


@router.get("/artifacts/models/{model_id}/lineage")
def get_lineage(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full lineage: training run + dataset + class map + cluster + evaluations."""
    import json as _json

    from app.models.cluster import Cluster
    from app.models.dataset import ClassMap

    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    run = db.get(ExperimentRun, artifact.run_id) if artifact.run_id else None
    version = (
        db.get(DatasetVersion, run.dataset_version_id) if run and run.dataset_version_id else None
    )
    dataset = db.get(Dataset, version.dataset_id) if version else None
    class_map = db.get(ClassMap, dataset.class_map_id) if dataset and dataset.class_map_id else None
    cluster = db.get(Cluster, run.cluster_id) if run and run.cluster_id else None

    classes: list[str] = []
    if class_map and class_map.classes:
        try:
            parsed = _json.loads(class_map.classes)
            if isinstance(parsed, list):
                classes = [str(c) for c in parsed]
        except Exception:
            classes = []

    params: dict = {}
    metrics: dict | list = {}
    if run:
        try:
            params = _json.loads(run.params_json) if run.params_json else {}
        except Exception:
            params = {}
        try:
            metrics = _json.loads(run.metrics_json) if run.metrics_json else {}
        except Exception:
            metrics = {}

    # Sibling artifacts produced by the same run (e.g. ONNX export of this .pt).
    siblings: list[dict] = []
    if run:
        sib_rows = list(
            db.scalars(
                select(ModelArtifact).where(
                    ModelArtifact.run_id == run.id, ModelArtifact.id != artifact.id
                )
            ).all()
        )
        siblings = [_artifact_dict(s) for s in sib_rows]

    # Evaluations of this artifact.
    evals = list(
        db.scalars(
            select(Evaluation)
            .where(Evaluation.artifact_id == artifact.id)
            .order_by(Evaluation.created_at.desc())
        ).all()
    )
    eval_summaries = []
    for e in evals:
        primary_name = None
        primary = None
        if e.metrics_json:
            try:
                m = _json.loads(e.metrics_json) or {}
                for name in ("mAP50", "mAP_5095", "accuracy", "precision", "recall", "f1"):
                    if name in m and isinstance(m[name], (int, float)):
                        primary_name = name
                        primary = float(m[name])
                        break
            except Exception:
                pass
        eval_summaries.append(
            {
                "id": e.id,
                "status": e.status,
                "dataset_version_id": e.dataset_version_id,
                "primary_metric_name": primary_name,
                "primary_metric": primary,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
        )

    return {
        "artifact": _artifact_dict(artifact),
        "experiment_run": (
            {
                "id": run.id,
                "name": run.name,
                "status": run.status,
                "params": params,
                "metrics": metrics,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            if run
            else None
        ),
        "dataset_version": (
            {
                "id": version.id,
                "version": version.version,
                "asset_count": version.asset_count,
                "locked": version.locked,
            }
            if version
            else None
        ),
        "dataset": (
            {
                "id": dataset.id,
                "name": dataset.name,
                "task_type": dataset.task_type,
            }
            if dataset
            else None
        ),
        "classes": classes,
        "cluster": (
            {
                "id": cluster.id,
                "name": cluster.name,
                "kind": cluster.kind,
                "gpu_vendor": cluster.gpu_vendor,
            }
            if cluster
            else None
        ),
        "siblings": siblings,
        "evaluations": eval_summaries,
    }
