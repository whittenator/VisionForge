from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.services import cluster_service
from app.services.jobs_service import create_job


def export_onnx(
    db: Session,
    experiment_id: str,
    dynamic_axes: bool | None = None,
    cluster_id: str | None = None,
) -> dict[str, Any]:
    if cluster_id:
        cluster_service.reserve_cluster(db, cluster_id, job_id="pending", kind="eval")

    payload = {
        "experimentId": experiment_id,
        "dynamicAxes": dynamic_axes,
        "clusterId": cluster_id,
    }
    job_row = create_job(db, "onnx_export", payload)
    payload["jobId"] = job_row.id

    if cluster_id:
        cluster = cluster_service.get_cluster(db, cluster_id)
        if cluster:
            cluster.active_job_id = job_row.id
            db.add(cluster)
            db.commit()

    queue = f"cluster.{cluster_id}" if cluster_id else None
    try:
        send_kwargs: dict[str, Any] = {"args": [payload]}
        if queue:
            send_kwargs["queue"] = queue
        celery_app.send_task("app.jobs.tasks.onnx_export.export_task", **send_kwargs)
        job_id = job_row.id
    except Exception:
        job_id = job_row.id

    return {
        "id": job_id,
        "jobId": job_id,
        "type": "onnx_export",
        "status": "queued",
        "progress": 0.0,
        "clusterId": cluster_id,
    }
