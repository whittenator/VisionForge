from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.deps import get_db
from app.models.artifact import ModelArtifact
from app.schemas.common import Job

router = APIRouter(prefix="/api", tags=["artifacts"])

@router.get("/artifacts/models", response_model=List[dict])
def list_models(db: Session = Depends(get_db)):
    # Simple list, in real impl add pagination/filters
    artifacts = db.query(ModelArtifact).all()
    return [
        {
            "id": a.id,
            "projectId": a.project_id,
            "runId": a.run_id,
            "version": a.version,
            "type": a.type,
            "checksum": a.checksum,
            "sizeBytes": a.size_bytes,
            "createdAt": a.created_at.isoformat(),
        }
        for a in artifacts
    ]

@router.post("/artifacts/models/{model_id}/export", response_model=Job)
def export_model(model_id: str, db: Session = Depends(get_db)):
    # For now, assume it's ONNX export, similar to ops
    artifact = db.query(ModelArtifact).filter(ModelArtifact.id == model_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Model not found")
    # Placeholder: in real impl, trigger export job
    # For now, return a dummy job
    return Job(id="dummy-job-id", status="queued", createdAt="2023-01-01T00:00:00Z")