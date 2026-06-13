from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.job import Job as JobModel
from app.models.user import User
from app.schemas.common import Job as JobSchema
from app.services.authz import require_job_access

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{jobId}", response_model=JobSchema)
def get_job(
    jobId: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(JobModel, jobId)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_job_access(db, current_user, job)
    return JobSchema(
        id=job.id,
        jobId=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
    )
