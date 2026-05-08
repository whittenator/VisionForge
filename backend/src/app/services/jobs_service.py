from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.job import Job as JobModel


def create_job(db: Session, job_type: str, payload: dict | None = None) -> JobModel:
    job = JobModel(
        type=job_type,
        payload_json=json.dumps(payload or {}),
        status="queued",
        progress=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_status(
    db: Session,
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    logs_uri: str | None = None,
) -> JobModel:
    job = db.get(JobModel, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if logs_uri is not None:
        job.logs_uri = logs_uri
    db.add(job)
    db.commit()
    db.refresh(job)

    if status in ("succeeded", "failed", "cancelled"):
        _release_cluster_for_job(db, job_id)
    return job


def _release_cluster_for_job(db: Session, job_id: str) -> None:
    """Release any cluster currently reserved for this job."""
    from app.models.cluster import Cluster

    cluster = db.query(Cluster).filter(Cluster.active_job_id == job_id).first()
    if cluster:
        cluster.active_job_id = None
        if cluster.status == "busy":
            cluster.status = "online"
        db.add(cluster)
        db.commit()
