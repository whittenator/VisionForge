from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.services.jobs_service import create_job


def export_onnx(db: Session, experiment_id: str, dynamic_axes: bool | None = None) -> dict[str, Any]:
    payload = {
        "experimentId": experiment_id,
        "dynamicAxes": dynamic_axes,
    }
    job_row = create_job(db, "onnx_export", payload)
    payload["jobId"] = job_row.id
    try:
        celery_app.send_task("app.jobs.tasks.onnx_export.export_task", args=[payload])
        job_id = job_row.id
    except Exception:
        job_id = job_row.id

    return {
        "id": job_id,
        "jobId": job_id,
        "type": "onnx_export",
        "status": "queued",
        "progress": 0.0,
    }
