from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.artifact import ModelArtifact
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.experiment import ExperimentRun
from app.models.user import User
from app.schemas.common import Job
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


@router.get("/artifacts/models/{model_id}/download")
def download_model(
    model_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    artifact = db.get(ModelArtifact, model_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not artifact.storage_path:
        raise HTTPException(status_code=404, detail="No file available for this artifact")
    try:
        import datetime
        import os

        from app.services.storage import get_minio_client

        client = get_minio_client()
        bucket = os.getenv("S3_BUCKET", os.getenv("MINIO_BUCKET", "visionforge"))
        url = client.presigned_get_object(
            bucket, artifact.storage_path, expires=datetime.timedelta(hours=1)
        )
        return {
            "download_url": url,
            "filename": artifact.storage_path.split("/")[-1],
            "size_bytes": artifact.size_bytes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {e}")


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
        db.get(DatasetVersion, run.dataset_version_id)
        if run and run.dataset_version_id
        else None
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
        "experiment_run": (
            {"id": run.id, "name": run.name, "status": run.status} if run else None
        ),
        "dataset_version": (
            {"id": version.id, "version": version.version} if version else None
        ),
        "dataset": (
            {"id": dataset.id, "name": dataset.name} if dataset else None
        ),
    }
