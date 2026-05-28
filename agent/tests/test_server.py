from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vf_agent import identity, server


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(identity, "IDENTITY_PATH", tmp_path / "identity.json")
    monkeypatch.setenv("VF_AGENT_TOKEN", "test-token")
    return TestClient(server.build_app())


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_health_no_auth_required(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["adopted"] is False
    assert "version" in body


def test_info_requires_token(client: TestClient) -> None:
    assert client.get("/info").status_code == 401
    assert client.get("/info", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_info_returns_discovery_shape(client: TestClient) -> None:
    resp = client.get("/info", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "cpu_cores",
        "ram_total_mb",
        "disk_total_gb",
        "gpu_vendor",
        "gpu_count",
        "gpus",
        "os",
        "agent_version",
    ):
        assert key in body, f"missing {key} in /info response"
    assert body["gpu_vendor"] in ("nvidia", "rocm", "cpu")
    assert body["os"]["name"]
    assert body["os"]["arch"]


def test_adopt_persists_identity(client: TestClient) -> None:
    resp = client.post(
        "/adopt",
        headers=_auth(),
        json={
            "cluster_id": "c-123",
            "register_token": "tok-abc",
            "api_url": "http://platform:8000/",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cluster_id"] == "c-123"

    ident = identity.load()
    assert ident is not None
    assert ident.cluster_id == "c-123"
    assert ident.register_token == "tok-abc"
    # Trailing slash stripped.
    assert ident.api_url == "http://platform:8000"

    # /health now reports adopted=True with the saved cluster_id.
    health = client.get("/health").json()
    assert health["adopted"] is True
    assert health["cluster_id"] == "c-123"


def test_telemetry_requires_token(client: TestClient) -> None:
    assert client.get("/telemetry").status_code == 401
    resp = client.get("/telemetry", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    for key in ("cpu_usage_pct", "ram_used_mb", "disk_used_gb", "gpu_usage_pct", "gpus"):
        assert key in body


def test_token_unset_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VF_AGENT_TOKEN", raising=False)
    fresh_app = server.build_app()
    fresh_client = TestClient(fresh_app)
    resp = fresh_client.get("/info", headers=_auth())
    assert resp.status_code == 503
