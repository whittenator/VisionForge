import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.experiment import ExperimentRun
from app.models.job import Job
from app.services.training_service import (
    TaskTypeMismatch,
    TrainingDispatchError,
    launch_training,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_launch_training_returns_job_id(tmp_path):
    db = _session()
    try:
        result = launch_training(db, project_id="p1", dataset_version_id="dv1", task="detect")
        assert result["status"] == "queued"
        assert result["type"] == "train"
        assert result["jobId"]
    finally:
        db.close()


def test_launch_training_defaults_to_ultralytics_framework():
    db = _session()
    try:
        result = launch_training(db, project_id="p1", dataset_version_id="dv1", task="detect")
        run = db.get(ExperimentRun, result["experimentId"])
        assert run.framework == "ultralytics"
        assert json.loads(run.params_json)["framework"] == "ultralytics"
    finally:
        db.close()


def test_launch_training_persists_timm_framework():
    db = _session()
    try:
        result = launch_training(
            db,
            project_id="p1",
            dataset_version_id="dv1",
            task="classify",
            framework="timm",
            params={"model": "resnet18"},
        )
        run = db.get(ExperimentRun, result["experimentId"])
        assert run.framework == "timm"
        params = json.loads(run.params_json)
        assert params["framework"] == "timm" and params["model"] == "resnet18"
    finally:
        db.close()


def test_launch_training_rejects_unsupported_task_for_framework():
    db = _session()
    try:
        # Timm is classification-only — detection must be rejected.
        with pytest.raises(TaskTypeMismatch):
            launch_training(
                db, project_id="p1", dataset_version_id="dv1", task="detect", framework="timm"
            )
    finally:
        db.close()


def test_launch_training_fails_job_when_dispatch_fails(monkeypatch):
    """If the broker can't be reached, the job is failed (not left queued)."""
    from app.jobs import celery_app as _celery_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("broker down")

    monkeypatch.setattr(_celery_mod.celery_app, "send_task", _boom, raising=False)

    db = _session()
    try:
        with pytest.raises(TrainingDispatchError):
            launch_training(db, project_id="p1", dataset_version_id="dv1", task="detect")
        # No phantom queued jobs left behind.
        jobs = db.query(Job).all()
        assert jobs and all(j.status == "failed" for j in jobs)
        runs = db.query(ExperimentRun).all()
        assert runs and all(r.status == "failed" for r in runs)
    finally:
        db.close()
