"""SSE stream tests for ``GET /api/experiments/runs/{runId}/metrics/stream``.

The stream endpoint authenticates via a real JWT (``?token=`` query param, as an
``EventSource`` client would), independently of the ``get_current_user`` override
other experiment tests use. A terminal run must emit at least one ``data:`` frame
containing the metrics and then end the stream immediately (with ``done: true``).
"""

from __future__ import annotations

import json
import uuid

from app.models.experiment import ExperimentRun
from app.services.auth import create_access_token, register
from tests.conftest import TestingSessionLocal, client, ensure_project


def _seed_user() -> tuple[str, str]:
    """Create a user and return (user_id, access_token)."""
    email = f"sse-{uuid.uuid4().hex[:8]}@example.com"
    with TestingSessionLocal() as db:
        user = register(db, name="SSE Tester", email=email, password="password123")
        return user.id, create_access_token(user.id, user.email)


def _mk_run(project_id: str, owner_id: str, *, status: str, metrics_json: str | None) -> str:
    ensure_project(project_id)
    with TestingSessionLocal() as db:
        run = ExperimentRun(
            id=str(uuid.uuid4()),
            project_id=project_id,
            owner_id=owner_id,
            name="Run",
            status=status,
            metrics_json=metrics_json,
        )
        db.add(run)
        db.commit()
        return run.id


def test_stream_terminal_run_emits_metrics_and_finishes():
    user_id, token = _seed_user()
    blob = json.dumps(
        {
            "epochs": [{"epoch": 1, "mAP50": 0.4}, {"epoch": 2, "mAP50": 0.6}],
            "summary": {"mAP50": 0.6},
        }
    )
    run_id = _mk_run(uuid.uuid4().hex, user_id, status="succeeded", metrics_json=blob)

    frames: list[dict] = []
    with client.stream(
        "GET", f"/api/experiments/runs/{run_id}/metrics/stream?token={token}"
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers.get("cache-control") == "no-cache"
        assert resp.headers.get("x-accel-buffering") == "no"
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                frames.append(json.loads(line[len("data:") :].strip()))
            # A terminal run ends the stream on its own; guard against a hang.
            if len(frames) >= 5:
                break

    # At least one metrics frame, and the stream terminated with done=True.
    assert frames, "expected at least one SSE data frame"
    assert any(len(f.get("metrics", [])) == 2 for f in frames)
    assert frames[-1].get("done") is True
    assert frames[-1]["status"] == "succeeded"


def test_stream_requires_auth():
    user_id, _ = _seed_user()
    run_id = _mk_run(uuid.uuid4().hex, user_id, status="succeeded", metrics_json=None)
    r = client.get(f"/api/experiments/runs/{run_id}/metrics/stream")
    assert r.status_code == 401


def test_stream_404_for_missing_run():
    _, token = _seed_user()
    r = client.get(f"/api/experiments/runs/missing/metrics/stream?token={token}")
    assert r.status_code == 404
