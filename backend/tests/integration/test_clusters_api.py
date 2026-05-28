"""Integration tests for the /api/clusters endpoints.

The cluster creation path now goes through `/api/clusters/discover`, which
probes a running agent. We stub the agent with `httpx.MockTransport` injected
into the service via monkeypatch so the suite stays hermetic.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db.deps import get_current_user
from app.main import app
from app.models.user import User
from app.services import cluster_service


def _fake_user() -> User:
    return User(id="test-user", email="tester@example.com", name="Tester", password_hash="x")


app.dependency_overrides[get_current_user] = _fake_user
client = TestClient(app)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _info_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "cpu_cores": 4,
        "ram_total_mb": 8192,
        "disk_total_gb": 100,
        "gpu_vendor": "nvidia",
        "gpu_count": 1,
        "gpu_model": "RTX 4090",
        "gpu_memory_mb": 24576,
        "gpus": [{"index": 0, "name": "RTX 4090", "memory_mb": 24576, "util_pct": 0.0}],
        "cpu_usage_pct": 0.0,
        "ram_used_mb": 0,
        "disk_used_gb": 0,
        "gpu_usage_pct": 0.0,
        "os": {"name": "Linux", "release": "6.18.5", "arch": "x86_64"},
        "agent_version": "0.1.0",
    }
    base.update(overrides)
    return base


def _stub_agent(monkeypatch: pytest.MonkeyPatch, info: dict[str, Any]) -> None:
    """Patch httpx.Client in cluster_service so /info + /adopt return canned data."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/info"):
            return httpx.Response(200, json=info)
        if request.url.path.endswith("/adopt"):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original = httpx.Client

    def factory(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(cluster_service.httpx, "Client", factory)


def _discover(monkeypatch: pytest.MonkeyPatch, info_overrides: dict[str, Any] | None = None, *, name_prefix: str = "ci", kind: str = "both") -> dict[str, Any]:
    _stub_agent(monkeypatch, _info_payload(**(info_overrides or {})))
    r = client.post(
        "/api/clusters/discover",
        json={
            "name": _unique(name_prefix),
            "host": "10.0.0.10",
            "port": 9443,
            "agent_token": "stub-token",
            "kind": kind,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_discover_returns_token_and_populates_specs_from_agent(monkeypatch):
    body = _discover(monkeypatch, {"gpu_count": 2, "gpu_model": "A100 80GB", "gpu_memory_mb": 81920})
    assert body["register_token"]
    assert body["status"] == "offline"
    assert body["gpu_vendor"] == "nvidia"
    assert body["gpu_count"] == 2
    assert body["gpu_model"] == "A100 80GB"
    assert body["agent_host"] == "10.0.0.10"
    assert body["agent_port"] == 9443
    assert body["agent_version"] == "0.1.0"
    assert body["os_name"] == "Linux"
    assert body["arch"] == "x86_64"


def test_discover_502s_when_agent_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    monkeypatch.setattr(
        cluster_service.httpx,
        "Client",
        lambda *a, **kw: original(*a, **{**kw, "transport": transport}),
    )

    r = client.post(
        "/api/clusters/discover",
        json={
            "name": _unique("ci-unreachable"),
            "host": "10.0.0.99",
            "port": 9443,
            "agent_token": "x",
            "kind": "both",
        },
    )
    assert r.status_code == 502, r.text
    assert "[reason=connect]" in r.json()["detail"]


def test_heartbeat_makes_cluster_available_for_training(monkeypatch):
    body = _discover(monkeypatch, {"gpu_vendor": "rocm", "gpu_count": 1}, name_prefix="ci-train", kind="train")
    cluster_id = body["id"]
    token = body["register_token"]

    hb = client.post(
        f"/api/clusters/{cluster_id}/heartbeat",
        json={
            "register_token": token,
            "status": "online",
            "cpu_usage_pct": 10.0,
            "ram_used_mb": 1024,
            "disk_used_gb": 10,
            "gpu_usage_pct": 5.0,
            "gpus": [
                {"index": 0, "name": "MI250", "memory_mb": 65536, "util_pct": 5.0, "mem_used_mb": 1024}
            ],
        },
    )
    assert hb.status_code == 200, hb.text

    avail = client.get("/api/clusters/available?kind=train").json()
    found = [c for c in avail if c["id"] == cluster_id]
    assert found and found[0]["available"] is True
    assert found[0]["gpu_vendor"] == "rocm"

    eval_avail = client.get("/api/clusters/available?kind=eval").json()
    found_eval = [c for c in eval_avail if c["id"] == cluster_id]
    assert found_eval and found_eval[0]["available"] is False


def test_heartbeat_rejects_invalid_token(monkeypatch):
    body = _discover(monkeypatch, name_prefix="ci-badtoken")
    bad = client.post(
        f"/api/clusters/{body['id']}/heartbeat",
        json={"register_token": "wrong", "status": "online"},
    )
    assert bad.status_code == 403


def test_train_with_unavailable_cluster_returns_409(monkeypatch):
    r = client.post("/api/projects", json={"name": _unique("ClusterProj"), "description": ""})
    proj_id = r.json()["id"]
    body = _discover(monkeypatch, name_prefix="ci-offline")
    cluster_id = body["id"]

    train = client.post(
        "/api/train",
        json={
            "projectId": proj_id,
            "datasetVersionId": "v1",
            "task": "detect",
            "clusterId": cluster_id,
            "params": {},
        },
    )
    assert train.status_code == 409, train.text


def test_train_with_available_cluster_routes_to_cluster_queue(monkeypatch):
    """Canonical Phase 4 proof: training launched against an available cluster must
    enqueue the Celery task on the dedicated cluster.{id} queue."""
    r = client.post("/api/projects", json={"name": _unique("ClusterProj2"), "description": ""})
    proj_id = r.json()["id"]

    body = _discover(monkeypatch, name_prefix="ci-online")
    cluster_id = body["id"]
    token = body["register_token"]

    client.post(
        f"/api/clusters/{cluster_id}/heartbeat",
        json={"register_token": token, "status": "online"},
    )

    # Capture the Celery dispatch so we can assert the queue routing without a real broker.
    captured: dict[str, Any] = {}
    from app.services import training_service

    def fake_send_task(name: str, **kwargs: Any) -> Any:
        captured["name"] = name
        captured["queue"] = kwargs.get("queue")
        captured["args"] = kwargs.get("args")

        class _R:
            id = "celery-id"

        return _R()

    monkeypatch.setattr(training_service.celery_app, "send_task", fake_send_task)

    train = client.post(
        "/api/train",
        json={
            "projectId": proj_id,
            "datasetVersionId": "v1",
            "task": "detect",
            "clusterId": cluster_id,
            "params": {},
        },
    )
    assert train.status_code == 202, train.text

    assert captured["name"] == "app.jobs.tasks.training.train_task"
    assert captured["queue"] == f"cluster.{cluster_id}"
    assert captured["args"][0]["clusterId"] == cluster_id

    info = client.get(f"/api/clusters/{cluster_id}").json()
    assert info["status"] == "busy"
    assert info["active_job_id"]


def test_rotate_token_invalidates_old_token(monkeypatch):
    body = _discover(monkeypatch, name_prefix="ci-rotate")
    cluster_id = body["id"]
    old_token = body["register_token"]

    rot = client.post(f"/api/clusters/{cluster_id}/rotate-token")
    assert rot.status_code == 200, rot.text
    new_token = rot.json()["register_token"]
    assert new_token != old_token

    bad = client.post(
        f"/api/clusters/{cluster_id}/heartbeat",
        json={"register_token": old_token, "status": "online"},
    )
    assert bad.status_code == 403
