from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.artifact import ModelArtifact
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.experiment import ExperimentRun
from app.models.user import User
from app.schemas.common import Job
from app.services import inference_service
from app.services.onnx_service import export_onnx as svc_export_onnx

router = APIRouter(prefix="/api", tags=["artifacts"])


@router.get("/artifacts/models")
def list_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifacts = db.query(ModelArtifact).all()
    return [
        {
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
        for a in artifacts
    ]


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


@router.post("/artifacts/models/{model_id}/export", response_model=Job)
def export_model(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    # Use the artifact's run_id as experiment_id for ONNX export
    experiment_id = artifact.run_id or model_id
    job = svc_export_onnx(db, experiment_id, dynamic_axes=True)
    return Job(**job)


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
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    run = db.get(ExperimentRun, artifact.run_id) if artifact.run_id else None
    version = (
        db.get(DatasetVersion, run.dataset_version_id) if run and run.dataset_version_id else None
    )
    dataset = db.get(Dataset, version.dataset_id) if version else None
    return {
        "artifact": {
            "id": artifact.id,
            "name": artifact.name,
            "version": artifact.version,
            "type": artifact.type,
            "format": artifact.format,
        },
        "experiment_run": ({"id": run.id, "name": run.name, "status": run.status} if run else None),
        "dataset_version": ({"id": version.id, "version": version.version} if version else None),
        "dataset": ({"id": dataset.id, "name": dataset.name} if dataset else None),
    }
