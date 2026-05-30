import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.experiment import ExperimentRun
from app.services.training_service import TaskTypeMismatch, launch_training


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
