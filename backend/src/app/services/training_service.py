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


class TrainingDispatchError(Exception):
    """Raised when the training Celery task can't be dispatched.

    The job row and run are marked ``failed`` and any cluster reservation is
    released before this is raised, so nothing is left permanently queued/busy.
    """


def _resolve_resume_key(db: Session, resume_from: str) -> str | None:
    """Resolve ``resume_from`` to a checkpoint object-storage key.

    ``resume_from`` is either a prior run id or an already-qualified storage key.
    For a run id, prefer the latest recorded checkpoint, then fall back to that
    run's ``best.pt`` artifact path. Returns None when nothing resumable exists.
    """
    ref = (resume_from or "").strip()
    if not ref:
        return None
    # An explicit storage key (contains a path separator or points at a weight).
    if "/" in ref or ref.endswith(".pt"):
        return ref

    prior = db.get(ExperimentRun, ref)
    if prior is None:
        return None
    try:
        checkpoints = json.loads(prior.checkpoints or "[]")
    except (ValueError, TypeError):
        checkpoints = []
    if checkpoints:
        latest = checkpoints[-1]
        if isinstance(latest, dict) and latest.get("key"):
            return str(latest["key"])
    # Fall back to the run's best-model artifact conventionally stored here.
    return f"models/{prior.id}/best.pt"


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
    framework: str = "ultralytics",
    resume_from: str | None = None,
) -> dict[str, Any]:
    # Reject obvious task/dataset mismatches so we don't burn cluster time on
    # a run we already know will fail (e.g. classify on a detection dataset).
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.services import training as training_pkg

    requested = (task or "").lower()

    # The chosen framework must support the requested task (e.g. Timm is
    # classification-only). Resolve through the registry so this stays generic.
    try:
        trainer = training_pkg.get_trainer(framework)
    except training_pkg.registry.UnknownFrameworkError as exc:
        raise TaskTypeMismatch(str(exc)) from exc
    if requested and requested not in trainer.supported_tasks:
        raise TaskTypeMismatch(f"framework '{trainer.key}' does not support task '{requested}'")

    if requested in ("detect", "classify"):
        version = db.get(DatasetVersion, dataset_version_id)
        dataset = db.get(Dataset, version.dataset_id) if version else None
        if dataset and dataset.task_type and dataset.task_type != requested:
            raise TaskTypeMismatch(
                f"task '{requested}' does not match dataset task_type " f"'{dataset.task_type}'"
            )

    # Build full params including task, framework and base_model so the worker
    # can read them.
    full_params = dict(params or {})
    full_params.setdefault("task", task)
    full_params.setdefault("framework", trainer.key)
    full_params.setdefault("base_model", base_model)

    # Resume support: ``resume_from`` may arrive as an explicit kwarg or inside
    # ``params`` (the /api/train endpoint forwards it via params). It references
    # either a prior run id or a checkpoint object-storage key. Resolve it to a
    # weights key so the worker can download and continue from those weights.
    resume_from = resume_from or full_params.get("resume_from")
    if resume_from:
        full_params["resume_from"] = resume_from
        resume_key = _resolve_resume_key(db, resume_from)
        if resume_key:
            full_params["resume_checkpoint_key"] = resume_key
            full_params["resume"] = True

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
        framework=trainer.key,
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

    # Enqueue async job. When a cluster is selected, route to its dedicated
    # queue so only its agent picks it up. If dispatch fails (broker down),
    # fail the job/run and release the cluster — otherwise the job sits
    # "queued" forever and the cluster stays "busy" (see onnx_service).
    queue = f"cluster.{cluster_id}" if cluster_id else None
    try:
        send_kwargs: dict[str, Any] = {"args": [payload]}
        if queue:
            send_kwargs["queue"] = queue
        celery_app.send_task("app.jobs.tasks.training.train_task", **send_kwargs)
        job_id = job_row.id
    except Exception as exc:
        from app.services.jobs_service import update_job_status

        if cluster_id:
            try:
                cluster_service.release_cluster(db, cluster_id)
            except Exception:
                pass
        try:
            update_job_status(db, job_row.id, status="failed", progress=0.0)
        except Exception:
            pass
        try:
            run.status = "failed"
            run.metrics_json = json.dumps({"error": f"task dispatch failed: {exc}"})
            db.add(run)
            db.commit()
        except Exception:
            db.rollback()
        raise TrainingDispatchError(f"failed to dispatch training task: {exc}") from exc

    return {
        "id": job_id,
        "jobId": job_id,
        "type": "train",
        "status": "queued",
        "progress": 0.0,
        "experimentId": run.id,
        "clusterId": cluster_id,
    }
