"""Integration tests for the /api/clusters endpoints.

We bypass `get_current_user` with a dependency override so these tests focus on
cluster API behaviour and don't depend on the auth/bcrypt stack being healthy
in the test environment.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.db.deps import get_current_user
from app.main import app
from app.models.user import User


def _fake_user() -> User:
    u = User(id="test-user", email="tester@example.com", name="Tester", password_hash="x")
    return u


app.dependency_overrides[get_current_user] = _fake_user
client = TestClient(app)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_register_cluster_returns_token_and_lists_offline():
    name = _unique("ci")
    r = client.post(
        "/api/clusters",
        json={
            "name": name,
            "description": "test",
            "kind": "both",
            "cpu_cores": 4,
            "ram_total_mb": 8192,
            "disk_total_gb": 100,
            "gpu_vendor": "nvidia",
            "gpu_count": 1,
            "gpu_model": "RTX 4090",
            "gpu_memory_mb": 24576,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    cluster_id = body["id"]
    assert body["register_token"]
    assert body["status"] == "offline"
    assert body["gpu_vendor"] == "nvidia"

    r2 = client.get("/api/clusters")
    assert r2.status_code == 200
    found = [c for c in r2.json() if c["id"] == cluster_id]
    assert found and found[0]["status"] == "offline"


def test_heartbeat_makes_cluster_available_for_training():
    r = client.post(
        "/api/clusters",
        json={"name": _unique("ci-train"), "kind": "train", "gpu_vendor": "rocm", "gpu_count": 1},
    )
    cluster_id = r.json()["id"]
    token = r.json()["register_token"]

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
                {
                    "index": 0,
                    "name": "MI250",
                    "memory_mb": 65536,
                    "util_pct": 5.0,
                    "mem_used_mb": 1024,
                }
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
    # train-only cluster should appear in eval list but be marked unavailable
    assert found_eval and found_eval[0]["available"] is False


def test_heartbeat_rejects_invalid_token():
    r = client.post("/api/clusters", json={"name": _unique("ci-badtoken")})
    cluster_id = r.json()["id"]
    bad = client.post(
        f"/api/clusters/{cluster_id}/heartbeat",
        json={"register_token": "wrong", "status": "online"},
    )
    assert bad.status_code == 403


def test_train_with_unavailable_cluster_returns_409():
    r = client.post("/api/projects", json={"name": _unique("ClusterProj"), "description": ""})
    proj_id = r.json()["id"]
    r2 = client.post("/api/clusters", json={"name": _unique("ci-offline")})
    cluster_id = r2.json()["id"]

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


def test_train_with_available_cluster_marks_it_busy():
    r = client.post("/api/projects", json={"name": _unique("ClusterProj2"), "description": ""})
    proj_id = r.json()["id"]

    r2 = client.post(
        "/api/clusters",
        json={"name": _unique("ci-online"), "kind": "both", "gpu_vendor": "nvidia", "gpu_count": 1},
    )
    cluster_id = r2.json()["id"]
    token = r2.json()["register_token"]

    client.post(
        f"/api/clusters/{cluster_id}/heartbeat",
        json={"register_token": token, "status": "online"},
    )

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

    info = client.get(f"/api/clusters/{cluster_id}").json()
    assert info["status"] == "busy"
    assert info["active_job_id"]
