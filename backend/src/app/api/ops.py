from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.common import (
    Job,
    OnnxExportRequest,
    TrainRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.ingest_service import get_presigned_upload
from app.services.onnx_service import export_onnx as svc_export_onnx
from app.services.training_service import launch_training

router = APIRouter(prefix="/api", tags=["ops"])

@router.post("/ingest/upload-url", response_model=UploadUrlResponse)
def get_upload_url(payload: UploadUrlRequest):
    data = get_presigned_upload(payload.datasetVersionId, payload.filename, payload.contentType)
    return UploadUrlResponse(**data)

@router.post("/train", response_model=Job, status_code=202)
def train(payload: TrainRequest, db: Session = Depends(get_db)):
    job = launch_training(db, payload.projectId, payload.datasetVersionId, payload.task, payload.params)
    return Job(**job)

@router.post("/export/onnx", response_model=Job, status_code=202)
def export_onnx(payload: OnnxExportRequest, db: Session = Depends(get_db)):
    job = svc_export_onnx(db, payload.experimentId, payload.dynamicAxes)
    return Job(**job)
