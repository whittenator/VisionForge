from uuid import uuid4

from fastapi import APIRouter

from app.schemas.common import Job

router = APIRouter(prefix="/api/al", tags=["active-learning"])

@router.post("/select", response_model=Job, status_code=202)
def select_samples(payload: dict):
    jid = str(uuid4())
    return Job(id=jid, jobId=jid, type="al_select", status="queued", progress=0.0)
