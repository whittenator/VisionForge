from typing import Any, Optional

from pydantic import BaseModel


class UploadUrlRequest(BaseModel):
    datasetVersionId: str
    filename: str
    contentType: Optional[str] = None

class UploadUrlResponse(BaseModel):
    url: str
    fields: dict[str, Any]

class TrainRequest(BaseModel):
    projectId: str
    datasetVersionId: str
    task: str
    params: dict[str, Any] = {}

class Job(BaseModel):
    id: str
    type: str
    status: str
    progress: float
    # Extra convenience for tests using jobId
    jobId: str

class OnnxExportRequest(BaseModel):
    experimentId: str
    dynamicAxes: Optional[bool] = None
