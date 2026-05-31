"""Unit tests for the Celery training task orchestration.

The task owns the framework-agnostic scaffolding: load the run, resolve the
split, drive a trainer, persist metrics, and march the Job/Run through their
status transitions. We stub the trainer (so no ML stack is needed) and run with
``MINIO_DISABLED=true`` so the test is hermetic and CI-light.
"""

from __future__ import annotations

import json
import uuid

from app.jobs.tasks import training as training_task
from app.models.cluster import Cluster
from app.models.experiment import ExperimentRun
from app.services import training as training_pkg
from app.services.jobs_service import create_job
from app.services.training.base import TrainResult
from tests.conftest import TestingSessionLocal


class _FakeTrainer:
    key = "fake"

    def run(self, ctx):  # noqa: D401 - matches Trainer.run signature
        ctx.report(progress=0.5, epoch={"epoch": 1, "loss": 0.1})
        return TrainResult(best_model_path=None, final_metrics={"mAP50": 0.42})


def _mk_run(db, **params) -> ExperimentRun:
    run = ExperimentRun(
        id=str(uuid.uuid4()),
        project_id="proj-1",
        owner_id="owner-1",
        name="Run",
        status="queued",
        params_json=json.dumps({"framework": "fake", "task": "detect", **params}),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_train_task_success_marks_run_and_job_succeeded(monkeypatch):
    monkeypatch.setattr(training_pkg, "get_trainer", lambda fw: _FakeTrainer())

    db = TestingSessionLocal()
    run = _mk_run(db)
    job = create_job(db, "training", {"experimentId": run.id})
    run_id, job_id = run.id, job.id
    db.close()

    result = training_task.train_task({"jobId": job_id, "experimentId": run_id})

    assert result["status"] == "succeeded"
    assert result["experiment_id"] == run_id

    check = TestingSessionLocal()
    try:
        refreshed_run = check.get(ExperimentRun, run_id)
        assert refreshed_run.status == "succeeded"
        assert refreshed_run.completed_at is not None
        metrics = json.loads(refreshed_run.metrics_json)
        # The fake trainer's final_metrics become the run summary, and the
        # reported epoch is recorded in the per-epoch history.
        assert metrics["summary"]["mAP50"] == 0.42
        assert metrics["epochs"] and metrics["epochs"][0]["epoch"] == 1

        from app.models.job import Job

        assert check.get(Job, job_id).status == "succeeded"
    finally:
        check.close()


def test_train_task_missing_run_fails_job(monkeypatch):
    monkeypatch.setattr(training_pkg, "get_trainer", lambda fw: _FakeTrainer())

    db = TestingSessionLocal()
    job = create_job(db, "training", {})
    job_id = job.id
    db.close()

    result = training_task.train_task({"jobId": job_id, "experimentId": "does-not-exist"})

    assert result["status"] == "failed"
    assert "not found" in result["error"]

    check = TestingSessionLocal()
    try:
        from app.models.job import Job

        assert check.get(Job, job_id).status == "failed"
    finally:
        check.close()


def test_train_task_releases_reserved_cluster_on_success(monkeypatch):
    monkeypatch.setattr(training_pkg, "get_trainer", lambda fw: _FakeTrainer())

    db = TestingSessionLocal()
    run = _mk_run(db)
    job = create_job(db, "training", {"experimentId": run.id})
    cluster = Cluster(
        id=str(uuid.uuid4()),
        name="gpu-box",
        status="busy",
        active_job_id=job.id,
    )
    db.add(cluster)
    db.commit()
    run_id, job_id, cluster_id = run.id, job.id, cluster.id
    db.close()

    training_task.train_task({"jobId": job_id, "experimentId": run_id})

    check = TestingSessionLocal()
    try:
        refreshed = check.get(Cluster, cluster_id)
        # Terminal job status must free the cluster so capacity isn't leaked.
        assert refreshed.active_job_id is None
        assert refreshed.status == "online"
    finally:
        check.close()
