from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.models.experiment import ExperimentRun
from app.services import cluster_service
from app.services.jobs_service import create_job


class TaskTypeMismatch(Exception):
    """Raised when a training run's task disagrees with its dataset's task_type."""


def launch_training(
    db: Session,
    project_id: str,
    dataset_version_id: str,
    task: str,
    params: dict[str, Any] | None = None,
    name: str = "Training Run",
    base_model: str = "yolov8n.pt",
    owner_id: str | None = None,
    cluster_id: str | None = None,
) -> dict[str, Any]:
    # Reject obvious task/dataset mismatches so we don't burn cluster time on
    # a run we already know will fail (e.g. classify on a detection dataset).
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion

    requested = (task or "").lower()
    if requested in ("detect", "classify"):
        version = db.get(DatasetVersion, dataset_version_id)
        dataset = db.get(Dataset, version.dataset_id) if version else None
        if dataset and dataset.task_type and dataset.task_type != requested:
            raise TaskTypeMismatch(
                f"task '{requested}' does not match dataset task_type " f"'{dataset.task_type}'"
            )

    # Build full params including task and base_model so the worker can read them
    full_params = dict(params or {})
    full_params.setdefault("task", task)
    full_params.setdefault("base_model", base_model)

    # If a cluster was selected, reserve it before creating the run so we fail
    # fast (and don't leave orphan rows) when the cluster is unavailable.
    if cluster_id:
        # Reserve with a placeholder job id; we'll update it once we have the real one.
        cluster_service.reserve_cluster(db, cluster_id, job_id="pending", kind="train")

    # Create the ExperimentRun row so the worker can look it up by ID.
    effective_owner = owner_id or "system"
    run = ExperimentRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        dataset_version_id=dataset_version_id,
        owner_id=effective_owner,
        cluster_id=cluster_id,
        name=name,
        status="queued",
        params_json=json.dumps(full_params),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    payload = {
        "projectId": project_id,
        "datasetVersionId": dataset_version_id,
        "task": task,
        "params": full_params,
        # Explicitly pass experiment and run IDs so the worker can find the row
        "experimentId": run.id,
        "runId": run.id,
        "clusterId": cluster_id,
    }

    # Create DB job row
    job_row = create_job(db, "train", payload)
    payload["jobId"] = job_row.id

    # Update the cluster reservation with the real job id
    if cluster_id:
        cluster = cluster_service.get_cluster(db, cluster_id)
        if cluster:
            cluster.active_job_id = job_row.id
            db.add(cluster)
            db.commit()

    # Enqueue async job; if broker not available, we still return a job id for contract.
    # When a cluster is selected, route to its dedicated queue so only its agent picks it up.
    queue = f"cluster.{cluster_id}" if cluster_id else None
    try:
        send_kwargs: dict[str, Any] = {"args": [payload]}
        if queue:
            send_kwargs["queue"] = queue
        celery_app.send_task("app.jobs.tasks.training.train_task", **send_kwargs)
        job_id = job_row.id
    except Exception:
        job_id = job_row.id

    return {
        "id": job_id,
        "jobId": job_id,
        "type": "train",
        "status": "queued",
        "progress": 0.0,
        "experimentId": run.id,
        "clusterId": cluster_id,
    }
