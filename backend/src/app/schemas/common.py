from typing import Any, Optional

from pydantic import BaseModel


class UploadUrlRequest(BaseModel):
    datasetVersionId: str
    filename: str
    contentType: Optional[str] = None


class UploadUrlResponse(BaseModel):
    url: str
    fields: dict[str, Any]
    objectKey: str  # add this so frontend knows the key


class TrainRequest(BaseModel):
    projectId: str
    datasetVersionId: str
    task: str  # "detect" or "classify"
    baseModel: str = "yolov8n.pt"
    params: dict[str, Any] = {}
    name: str = "Training Run"


class OnnxExportRequest(BaseModel):
    experimentId: str
    dynamicAxes: Optional[bool] = True


class Job(BaseModel):
    id: str
    jobId: str
    type: str
    status: str
    progress: float
    errorMessage: Optional[str] = None
    createdAt: Optional[str] = None
