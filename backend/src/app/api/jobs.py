from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.job import Job as JobModel
from app.schemas.common import Job as JobSchema

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{jobId}", response_model=JobSchema)
def get_job(jobId: str = Path(...), db: Session = Depends(get_db)):
    job = db.get(JobModel, jobId)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobSchema(
        id=job.id,
        jobId=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
    )


@router.delete("/jobs/{job_id}", status_code=204)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    job = db.get(JobModel, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status '{job.status}'",
        )
    try:
        from app.jobs.celery_app import celery_app

        celery_app.control.revoke(job_id, terminate=True, signal="SIGTERM")
    except Exception:
        pass
    job.status = "failed"
    job.error_message = "Cancelled by user"
    db.add(job)
    db.commit()
