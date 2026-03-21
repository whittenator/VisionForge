from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.experiment import ExperimentRun
from app.models.asset import Asset
from app.models.annotation import Annotation
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.services.jobs_service import create_job, update_job_status
from app.jobs.celery_app import celery_app


def launch_evaluation(db: Session, run_id: str) -> Any:
    """Launch an async evaluation job for an experiment run."""
    run = db.get(ExperimentRun, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    job = create_job(db, "evaluate", {"run_id": run_id})

    try:
        celery_app.send_task("app.jobs.tasks.evaluation.evaluate_task", args=[{"job_id": job.id, "run_id": run_id}])
    except Exception:
        pass

    return job


def get_evaluation(db: Session, run_id: str) -> dict | None:
    """Return stored evaluation results for a run."""
    run = db.get(ExperimentRun, run_id)
    if run is None:
        return None
    if not run.evaluation_json:
        return None
    try:
        return json.loads(run.evaluation_json)
    except Exception:
        return None
