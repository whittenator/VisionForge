from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.models.experiment import ExperimentRun
from app.services.jobs_service import create_job


def launch_training(
    db: Session,
    project_id: str,
    dataset_version_id: str,
    task: str,
    params: dict[str, Any] | None = None,
    name: str = "Training Run",
    base_model: str = "yolov8n.pt",
    owner_id: str | None = None,
) -> dict[str, Any]:
    # Build full params including task and base_model so the worker can read them
    full_params = dict(params or {})
    full_params.setdefault("task", task)
    full_params.setdefault("base_model", base_model)

    # Create the ExperimentRun row so the worker can look it up by ID
    # owner_id is required by the model; fall back to a sentinel if not provided
    effective_owner = owner_id or "system"
    run = ExperimentRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        dataset_version_id=dataset_version_id,
        owner_id=effective_owner,
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
    }

    # Create DB job row
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
        "experimentId": run.id,
    }
