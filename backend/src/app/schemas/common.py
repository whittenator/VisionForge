from typing import Any

from pydantic import BaseModel


class UploadUrlRequest(BaseModel):
    datasetVersionId: str
    filename: str
    contentType: str | None = None


class UploadUrlResponse(BaseModel):
    url: str
    fields: dict[str, Any]
    objectKey: str  # add this so frontend knows the key


class TrainRequest(BaseModel):
    projectId: str
    datasetVersionId: str
    task: str  # "detect" | "classify" | "segment" | "pose"
    framework: str = "ultralytics"  # which training backend to use
    baseModel: str = "yolov8n.pt"
    params: dict[str, Any] = {}
    name: str = "Training Run"
    clusterId: str | None = None


class OnnxExportRequest(BaseModel):
    experimentId: str
    dynamicAxes: bool | None = True
    clusterId: str | None = None


class Job(BaseModel):
    """Generic async job response.

    Includes optional linkage fields so callers can wire the job back to the
    domain object that spawned it (training run / evaluation / cluster) without
    a second round trip and without `response_model=Job` silently dropping
    the field.
    """

    id: str
    jobId: str
    type: str
    status: str
    progress: float
    errorMessage: str | None = None
    createdAt: str | None = None
    clusterId: str | None = None
    experimentId: str | None = None
    evaluationId: str | None = None
