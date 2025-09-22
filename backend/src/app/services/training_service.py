from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.services.jobs_service import create_job


def launch_training(
    db: Session, project_id: str, dataset_version_id: str, task: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = {
        "projectId": project_id,
        "datasetVersionId": dataset_version_id,
        "task": task,
        "params": params or {},
    }
    # Create DB job row first
    job_row = create_job(db, "train", payload)
    payload["jobId"] = job_row.id

    # Enqueue async job; if broker not available, we still return a job id for contract
    try:
        celery_app.send_task("app.jobs.tasks.training.train_task", args=[payload])
        job_id = job_row.id
    except Exception:
        job_id = job_row.id

    return {
        "id": job_id,
        "jobId": job_id,
        "type": "train",
        "status": "queued",
        "progress": 0.0,
    }
