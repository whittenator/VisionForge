from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.services import cluster_service
from app.services.jobs_service import create_job


class OnnxDispatchError(Exception):
    """Raised when the ONNX export Celery task can't be dispatched.

    The associated job row is marked ``failed`` before this is raised so the
    UI doesn't show a phantom queued export.
    """


def export_onnx(
    db: Session,
    experiment_id: str,
    dynamic_axes: bool | None = None,
    *,
    opset: int | None = None,
    cluster_id: str | None = None,
) -> dict[str, Any]:
    """Queue an ONNX export of the artifact produced by ``experiment_id``.

    Mirrors training/evaluation behaviour: optionally reserve a cluster and
    route the Celery task to that cluster's queue. If reservation succeeds
    but task dispatch fails (broker down), the cluster is released and the
    job row is flipped to ``failed`` — leaving stale ``queued`` rows around
    is exactly the bug Copilot's review flagged.
    """
    payload: dict[str, Any] = {
        "experimentId": experiment_id,
        "dynamicAxes": dynamic_axes,
        "opset": opset,
        "clusterId": cluster_id,
    }
    job_row = create_job(db, "onnx_export", payload)
    payload["jobId"] = job_row.id

    if cluster_id:
        try:
            cluster_service.reserve_cluster(db, cluster_id, job_id=job_row.id, kind="eval")
        except Exception:
            from app.services.jobs_service import update_job_status

            try:
                update_job_status(db, job_row.id, status="failed", progress=0.0)
            except Exception:
                pass
            raise

    queue = f"cluster.{cluster_id}" if cluster_id else None
    try:
        send_kwargs: dict[str, Any] = {"args": [payload]}
        if queue:
            send_kwargs["queue"] = queue
        celery_app.send_task("app.jobs.tasks.onnx_export.export_task", **send_kwargs)
    except Exception as exc:
        # Release any reservation, then flip the job to failed so it doesn't
        # sit in the dashboard as a phantom queued export.
        if cluster_id:
            try:
                cluster_service.release_cluster(db, cluster_id)
            except Exception:
                pass
        from app.services.jobs_service import update_job_status

        try:
            update_job_status(db, job_row.id, status="failed", progress=0.0)
        except Exception:
            pass
        raise OnnxDispatchError(f"failed to dispatch ONNX export task: {exc}") from exc

    return {
        "id": job_row.id,
        "jobId": job_row.id,
        "type": "onnx_export",
        "status": "queued",
        "progress": 0.0,
        "clusterId": cluster_id,
    }
