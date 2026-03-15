from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.job import Job as JobModel
from app.services.jobs_service import create_job


def launch_evaluation(db: Session, experiment_run_id: str) -> JobModel:
    job = create_job(db, "evaluation", {"experiment_run_id": experiment_run_id})
    try:
        from app.jobs.celery_app import celery_app
        from app.jobs.tasks.evaluation import evaluate_task

        evaluate_task.apply_async(
            args=[{"experiment_run_id": experiment_run_id, "job_id": job.id}],
            queue="default",
        )
    except Exception:
        pass
    return job
