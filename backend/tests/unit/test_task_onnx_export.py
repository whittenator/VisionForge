"""Unit tests for the ONNX export Celery task.

Runs with ``MINIO_DISABLED=true`` so the task takes its storage-less path:
no weights are downloaded or uploaded, but it still must create the ONNX
``ModelArtifact`` row and drive the Job through its status transitions.
"""

from __future__ import annotations

import uuid

from app.jobs.tasks import onnx_export as onnx_task
from app.models.artifact import ModelArtifact
from app.models.cluster import Cluster
from app.models.experiment import ExperimentRun
from app.services.jobs_service import create_job
from tests.conftest import TestingSessionLocal


def _mk_run(db) -> ExperimentRun:
    run = ExperimentRun(
        id=str(uuid.uuid4()),
        project_id="proj-onnx",
        owner_id="owner-1",
        name="Run",
        status="succeeded",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_export_task_creates_onnx_artifact_and_succeeds():
    db = TestingSessionLocal()
    run = _mk_run(db)
    job = create_job(db, "onnx_export", {"experimentId": run.id})
    run_id, job_id = run.id, job.id
    db.close()

    result = onnx_task.export_task({"jobId": job_id, "experimentId": run_id})

    assert result["status"] == "succeeded"

    check = TestingSessionLocal()
    try:
        artifact = (
            check.query(ModelArtifact)
            .filter(ModelArtifact.run_id == run_id, ModelArtifact.type == "onnx")
            .first()
        )
        assert artifact is not None

        from app.models.job import Job

        assert check.get(Job, job_id).status == "succeeded"
    finally:
        check.close()


def test_export_task_missing_run_fails_job():
    db = TestingSessionLocal()
    job = create_job(db, "onnx_export", {})
    job_id = job.id
    db.close()

    result = onnx_task.export_task({"jobId": job_id, "experimentId": "nope"})

    assert result["status"] == "failed"
    assert "not found" in result["error"]

    check = TestingSessionLocal()
    try:
        from app.models.job import Job

        assert check.get(Job, job_id).status == "failed"
    finally:
        check.close()


def test_export_task_releases_reserved_cluster_on_success():
    db = TestingSessionLocal()
    run = _mk_run(db)
    job = create_job(db, "onnx_export", {"experimentId": run.id})
    cluster = Cluster(id=str(uuid.uuid4()), name="gpu", status="busy", active_job_id=job.id)
    db.add(cluster)
    db.commit()
    run_id, job_id, cluster_id = run.id, job.id, cluster.id
    db.close()

    onnx_task.export_task({"jobId": job_id, "experimentId": run_id})

    check = TestingSessionLocal()
    try:
        refreshed = check.get(Cluster, cluster_id)
        assert refreshed.active_job_id is None
        assert refreshed.status == "online"
    finally:
        check.close()
