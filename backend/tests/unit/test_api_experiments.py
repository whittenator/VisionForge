"""Request-level tests for the experiments router (``api/experiments.py``).

Covers run creation, the paginated list shape + project filter, the 404/200
detail paths, and the ``/metrics`` endpoint's handling of the several
``metrics_json`` shapes it must tolerate.
"""

from __future__ import annotations

import json
import uuid

from app.db.deps import get_current_user
from app.main import app
from app.models.experiment import ExperimentRun
from app.models.user import User
from tests.conftest import TestingSessionLocal, client


def _fake_user() -> User:
    return User(id="exp-tester", email="exp@example.com", name="T", password_hash="x")


app.dependency_overrides[get_current_user] = _fake_user


def _mk_run(project_id: str, *, metrics_json: str | None = None) -> str:
    db = TestingSessionLocal()
    try:
        run = ExperimentRun(
            id=str(uuid.uuid4()),
            project_id=project_id,
            owner_id="exp-tester",
            name="Run",
            status="succeeded",
            metrics_json=metrics_json,
        )
        db.add(run)
        db.commit()
        return run.id
    finally:
        db.close()


def test_create_run():
    project_id = uuid.uuid4().hex
    r = client.post(
        "/api/experiments/runs",
        json={"project_id": project_id, "name": "My Run", "params": {"lr": 0.01}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["name"] == "My Run"


def test_list_runs_filtered_by_project():
    project_id = uuid.uuid4().hex
    _mk_run(project_id)
    _mk_run(project_id)
    _mk_run(uuid.uuid4().hex)  # different project

    r = client.get(f"/api/experiments/runs?project_id={project_id}&page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["page"] == 1 and body["page_size"] == 10
    assert all(item["project_id"] == project_id for item in body["items"])


def test_get_run_404_and_200():
    assert client.get("/api/experiments/runs/missing").status_code == 404
    run_id = _mk_run(uuid.uuid4().hex)
    r = client.get(f"/api/experiments/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["id"] == run_id


def test_metrics_endpoint_parses_epochs_dict():
    blob = json.dumps(
        {
            "epochs": [{"epoch": 1, "mAP50": 0.4}, {"epoch": 2, "mAP50": 0.6}],
            "summary": {"mAP50": 0.6},
        }
    )
    run_id = _mk_run(uuid.uuid4().hex, metrics_json=blob)
    r = client.get(f"/api/experiments/runs/{run_id}/metrics")
    assert r.status_code == 200
    body = r.json()
    assert len(body["metrics"]) == 2
    assert body["summary"]["mAP50"] == 0.6


def test_metrics_endpoint_tolerates_error_blob():
    run_id = _mk_run(uuid.uuid4().hex, metrics_json='{"error": "boom"}')
    r = client.get(f"/api/experiments/runs/{run_id}/metrics")
    assert r.status_code == 200
    # An error blob yields no chartable epochs.
    assert r.json()["metrics"] == []


def test_metrics_endpoint_404_when_missing():
    assert client.get("/api/experiments/runs/missing/metrics").status_code == 404
