from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.celery_app import celery_app
from app.models.artifact import ModelArtifact
from app.models.dataset_version import DatasetVersion
from app.models.evaluation import Evaluation
from app.schemas.evaluation import EvaluationCreate
from app.services import cluster_service
from app.services.jobs_service import create_job


class EvaluationError(Exception):
    pass


def create_evaluation(
    db: Session,
    payload: EvaluationCreate,
) -> tuple[Evaluation, dict[str, Any]]:
    """Create an Evaluation row and dispatch the eval Celery task.

    Sequence:
      1. Validate inputs (artifact + dataset version exist).
      2. Create the Evaluation row (queued, no cluster yet).
      3. Create the Job row so we have a real job id.
      4. Reserve the cluster atomically with the real job id (or release on
         failure).
      5. Dispatch the Celery task. If dispatch fails AND a cluster was
         reserved, release it and mark the evaluation/job as failed instead
         of leaking capacity.
    """
    artifact = db.get(ModelArtifact, payload.artifact_id)
    if not artifact:
        raise EvaluationError("artifact not found")
    version = db.get(DatasetVersion, payload.dataset_version_id)
    if not version:
        raise EvaluationError("dataset version not found")

    eval_row = Evaluation(
        project_id=artifact.project_id,
        artifact_id=artifact.id,
        dataset_version_id=version.id,
        cluster_id=payload.cluster_id,
        status="queued",
    )
    db.add(eval_row)
    db.commit()
    db.refresh(eval_row)

    task_payload: dict[str, Any] = {
        "evaluationId": eval_row.id,
        "artifactId": artifact.id,
        "datasetVersionId": version.id,
        "split": payload.split,
        "iouThreshold": payload.iou_threshold,
        "scoreThreshold": payload.score_threshold,
        "maxSamples": payload.max_samples,
        "sampleFpFnCount": payload.sample_fpfn_count,
        "clusterId": payload.cluster_id,
    }
    job_row = create_job(db, "evaluation", task_payload)
    eval_row.job_id = job_row.id
    db.add(eval_row)
    db.commit()
    db.refresh(eval_row)
    task_payload["jobId"] = job_row.id

    # Reserve the cluster with the real job id. If reservation fails, the
    # error propagates and the caller turns it into a 409.
    if payload.cluster_id:
        try:
            cluster_service.reserve_cluster(
                db, payload.cluster_id, job_id=job_row.id, kind="eval"
            )
        except Exception:
            # Mark the queued rows as failed so the dashboard doesn't show a
            # phantom queued evaluation.
            from app.services.jobs_service import update_job_status

            write_result(
                db,
                eval_row.id,
                status="failed",
                error_message="cluster reservation failed",
            )
            try:
                update_job_status(db, job_row.id, status="failed", progress=0.0)
            except Exception:
                pass
            raise

    queue = f"cluster.{payload.cluster_id}" if payload.cluster_id else None
    try:
        send_kwargs: dict[str, Any] = {"args": [task_payload]}
        if queue:
            send_kwargs["queue"] = queue
        celery_app.send_task("app.jobs.tasks.evaluation.evaluate_task", **send_kwargs)
    except Exception as exc:
        # Broker may not be available. If we already reserved a cluster, the
        # worker will never pick the task up — release the cluster and mark
        # the evaluation failed instead of holding capacity indefinitely.
        if payload.cluster_id:
            try:
                cluster_service.release_cluster(db, payload.cluster_id)
            except Exception:
                pass
            from app.services.jobs_service import update_job_status

            write_result(
                db,
                eval_row.id,
                status="failed",
                error_message=f"task dispatch failed: {exc}",
            )
            try:
                update_job_status(db, job_row.id, status="failed", progress=0.0)
            except Exception:
                pass
            raise EvaluationError(f"failed to dispatch evaluation task: {exc}") from exc
        # No cluster reserved — the row is the contract; a worker can still
        # pick it up when the broker is back. Leave it queued.

    job_dict = {
        "id": job_row.id,
        "jobId": job_row.id,
        "type": "evaluation",
        "status": eval_row.status,
        "progress": 0.0,
        "evaluationId": eval_row.id,
        "clusterId": payload.cluster_id,
    }
    return eval_row, job_dict


def list_evaluations(
    db: Session,
    *,
    artifact_id: str | None = None,
    dataset_version_id: str | None = None,
    project_id: str | None = None,
) -> list[Evaluation]:
    q = select(Evaluation).order_by(Evaluation.created_at.desc())
    if artifact_id:
        q = q.where(Evaluation.artifact_id == artifact_id)
    if dataset_version_id:
        q = q.where(Evaluation.dataset_version_id == dataset_version_id)
    if project_id:
        q = q.where(Evaluation.project_id == project_id)
    return list(db.scalars(q).all())


def get_evaluation(db: Session, eval_id: str) -> Evaluation | None:
    return db.get(Evaluation, eval_id)


def to_dict(eval_row: Evaluation) -> dict[str, Any]:
    def parse(s: str | None, default: Any) -> Any:
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default

    return {
        "id": eval_row.id,
        "project_id": eval_row.project_id,
        "artifact_id": eval_row.artifact_id,
        "dataset_version_id": eval_row.dataset_version_id,
        "cluster_id": eval_row.cluster_id,
        "job_id": eval_row.job_id,
        "status": eval_row.status,
        "metrics": parse(eval_row.metrics_json, None),
        "per_class": parse(eval_row.per_class_json, None),
        "confusion": parse(eval_row.confusion_json, None),
        "classes": parse(eval_row.classes_json, None),
        "samples": parse(eval_row.samples_json, None),
        "error_message": eval_row.error_message,
        "started_at": eval_row.started_at,
        "completed_at": eval_row.completed_at,
        "created_at": eval_row.created_at,
    }


def summarize(eval_row: Evaluation) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if eval_row.metrics_json:
        try:
            metrics = json.loads(eval_row.metrics_json) or {}
        except Exception:
            metrics = {}
    primary_name: str | None = None
    primary: float | None = None
    for name in ("mAP50", "accuracy", "precision", "recall", "f1"):
        if name in metrics and isinstance(metrics[name], (int, float)):
            primary_name = name
            primary = float(metrics[name])
            break
    return {
        "id": eval_row.id,
        "artifact_id": eval_row.artifact_id,
        "dataset_version_id": eval_row.dataset_version_id,
        "status": eval_row.status,
        "primary_metric_name": primary_name,
        "primary_metric": primary,
        "created_at": eval_row.created_at,
        "completed_at": eval_row.completed_at,
    }


def write_result(
    db: Session,
    eval_id: str,
    *,
    status: str,
    metrics: dict[str, Any] | None = None,
    per_class: dict[str, Any] | None = None,
    confusion: list[list[int]] | None = None,
    classes: list[str] | None = None,
    samples: list[dict[str, Any]] | None = None,
    error_message: str | None = None,
) -> Evaluation | None:
    """Worker-side helper to persist eval results."""
    row = db.get(Evaluation, eval_id)
    if not row:
        return None
    row.status = status
    if metrics is not None:
        row.metrics_json = json.dumps(metrics)
    if per_class is not None:
        row.per_class_json = json.dumps(per_class)
    if confusion is not None:
        row.confusion_json = json.dumps(confusion)
    if classes is not None:
        row.classes_json = json.dumps(classes)
    if samples is not None:
        row.samples_json = json.dumps(samples)
    if error_message is not None:
        row.error_message = error_message
    if status in ("succeeded", "failed"):
        row.completed_at = datetime.now(timezone.utc)
    if status == "running" and row.started_at is None:
        row.started_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
