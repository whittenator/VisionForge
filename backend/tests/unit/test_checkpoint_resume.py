"""Tests for training checkpoint saving + resume wiring.

These cover the plumbing (capabilities flag, ``resume_from`` acceptance and its
resolution into a checkpoint key persisted in ``params_json``) without requiring
the heavy ML wheels or a running worker.
"""

from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.experiment import ExperimentRun
from app.services import training as training_pkg
from app.services.training.base import Capabilities
from app.services.training_service import _resolve_resume_key, launch_training


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_capabilities_has_supports_resume_default_false():
    # The dataclass default keeps every other backend unaffected.
    caps = Capabilities(
        key="x",
        label="X",
        supported_tasks=["classify"],
        models_by_task={},
        groups=[],
        device_options=["cpu"],
    )
    assert caps.supports_resume is False


def test_ultralytics_capabilities_supports_resume():
    trainer = training_pkg.get_trainer("ultralytics")
    caps = trainer.capabilities()
    assert caps.supports_resume is True
    # And ``resume`` is an allowed train kwarg.
    from app.services.training.ultralytics_trainer import ULTRALYTICS_TRAIN_ARGS

    assert "resume" in ULTRALYTICS_TRAIN_ARGS


def test_timm_capabilities_defaults_resume_false():
    trainer = training_pkg.get_trainer("timm")
    assert trainer.capabilities().supports_resume is False


def test_launch_training_accepts_resume_from_kwarg_persists_params():
    db = _session()
    try:
        result = launch_training(
            db,
            project_id="p1",
            dataset_version_id="dv1",
            task="detect",
            resume_from="models/run-xyz/best.pt",
        )
        run = db.get(ExperimentRun, result["experimentId"])
        params = json.loads(run.params_json)
        assert params["resume_from"] == "models/run-xyz/best.pt"
        # An explicit storage key resolves to itself and enables resume.
        assert params["resume_checkpoint_key"] == "models/run-xyz/best.pt"
        assert params["resume"] is True
    finally:
        db.close()


def test_launch_training_reads_resume_from_params():
    db = _session()
    try:
        result = launch_training(
            db,
            project_id="p1",
            dataset_version_id="dv1",
            task="detect",
            params={"resume_from": "models/run-abc/checkpoints/epoch_3.pt"},
        )
        run = db.get(ExperimentRun, result["experimentId"])
        params = json.loads(run.params_json)
        assert params["resume_from"] == "models/run-abc/checkpoints/epoch_3.pt"
        assert params["resume_checkpoint_key"] == "models/run-abc/checkpoints/epoch_3.pt"
    finally:
        db.close()


def test_resolve_resume_key_from_prior_run_checkpoint():
    db = _session()
    try:
        prior = ExperimentRun(
            id="prior-run",
            project_id="p1",
            owner_id="system",
            name="prior",
            status="succeeded",
            checkpoints=json.dumps(
                [
                    {"epoch": 1, "key": "models/prior-run/checkpoints/epoch_1.pt", "metric": 0.1},
                    {"epoch": 2, "key": "models/prior-run/checkpoints/epoch_2.pt", "metric": 0.5},
                ]
            ),
        )
        db.add(prior)
        db.commit()
        # Latest recorded checkpoint wins.
        assert _resolve_resume_key(db, "prior-run") == "models/prior-run/checkpoints/epoch_2.pt"
    finally:
        db.close()


def test_resolve_resume_key_falls_back_to_best_artifact():
    db = _session()
    try:
        prior = ExperimentRun(
            id="run-no-ckpt",
            project_id="p1",
            owner_id="system",
            name="prior",
            status="succeeded",
        )
        db.add(prior)
        db.commit()
        assert _resolve_resume_key(db, "run-no-ckpt") == "models/run-no-ckpt/best.pt"
    finally:
        db.close()


def test_launch_training_without_resume_is_unchanged():
    db = _session()
    try:
        result = launch_training(db, project_id="p1", dataset_version_id="dv1", task="detect")
        run = db.get(ExperimentRun, result["experimentId"])
        params = json.loads(run.params_json)
        assert "resume_from" not in params
        assert "resume_checkpoint_key" not in params
    finally:
        db.close()
