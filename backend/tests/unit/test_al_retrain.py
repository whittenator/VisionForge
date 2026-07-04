"""Unit tests for the active-learning retrain feedback loop.

Covers ``POST /api/al/runs/{id}/retrain``: it launches a training run from an AL
run's resolved items, records the spawned run id on ``last_train_run_id``, and
returns 409 when nothing has been resolved yet. Celery dispatch is stubbed by the
autouse fixture in ``tests/conftest.py`` so no broker is required.
"""

from __future__ import annotations

import json
import uuid

from app.api import al as al_api
from app.models.alitem import ALItem
from app.models.alrun import ALRun
from app.models.user import User
from tests.conftest import TestingSessionLocal, ensure_project


def _fake_user() -> User:
    return User(id=str(uuid.uuid4()), name="Dev", email="dev@example.com")


def _mk_run(db, *, project_id: str = "p", version_id: str = "ver-1") -> ALRun:
    run = ALRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        strategy="uncertainty",
        params_json=json.dumps({"dataset_version_id": version_id, "k": 5}),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _mk_item(db, al_run_id: str, *, resolved: bool) -> ALItem:
    item = ALItem(
        id=str(uuid.uuid4()),
        al_run_id=al_run_id,
        asset_id=str(uuid.uuid4()),
        priority=0.5,
        resolved_status="resolved" if resolved else "pending",
    )
    db.add(item)
    db.commit()
    return item


def test_retrain_launches_training_and_records_run_id():
    ensure_project("p")
    with TestingSessionLocal() as db:
        run = _mk_run(db)
        _mk_item(db, run.id, resolved=True)

        out = al_api.retrain_from_resolved(
            run.id, al_api.ALRetrainRequest(task="detect"), db, _fake_user()
        )

        assert out["al_run_id"] == run.id
        assert out["train_run_id"]
        assert out["job_id"]
        assert out["resolved_count"] == 1

        refreshed = db.get(ALRun, run.id)
        assert refreshed.last_train_run_id == out["train_run_id"]


def test_retrain_without_resolved_items_returns_409():
    import pytest
    from fastapi import HTTPException

    ensure_project("p")
    with TestingSessionLocal() as db:
        run = _mk_run(db)
        _mk_item(db, run.id, resolved=False)

        with pytest.raises(HTTPException) as excinfo:
            al_api.retrain_from_resolved(run.id, al_api.ALRetrainRequest(), db, _fake_user())
        assert excinfo.value.status_code == 409
        assert "no resolved items" in excinfo.value.detail


def test_progress_reports_counts_and_last_train_run_id():
    ensure_project("p")
    with TestingSessionLocal() as db:
        run = _mk_run(db)
        _mk_item(db, run.id, resolved=True)
        _mk_item(db, run.id, resolved=False)

        prog = al_api.get_al_progress(run.id, db, _fake_user())
        assert prog["total"] == 2
        assert prog["resolved"] == 1
        assert prog["pending"] == 1
        assert prog["last_train_run_id"] is None
