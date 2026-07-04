"""Unit tests for per-workspace storage backend selection.

Covers the strategy layer (``services/storage_backends``), the ``workspace_id``
routing added to ``storage.presign_put_url``, and the settings API
(``api/settings``): access control, secret redaction/preservation, backend
validation, and the connection-test endpoint. Runs hermetically — no network is
touched (``MINIO_DISABLED`` for presign, monkeypatched ``test_connection``).
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.api.settings import router as settings_router
from app.db.deps import get_current_user
from app.main import app
from app.models.user import User
from app.models.workspace import Workspace
from app.services import storage
from app.services import storage_backends as sb
from tests.conftest import TestingSessionLocal, client

# The settings router is wired into the app by main.py in production; the test
# app fixture predates that wiring, so register it here (idempotently) so the
# request-level tests below can reach the endpoints.
if not any(getattr(r, "path", "").startswith("/api/settings") for r in app.routes):
    app.include_router(settings_router)

# ---------------------------------------------------------------------------
# Strategy layer
# ---------------------------------------------------------------------------


def test_settings_from_invalid_backend_falls_back_to_minio():
    settings = sb.settings_from("nonsense", {})
    assert settings.backend == "minio"


def test_settings_from_minio_uses_env_defaults(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "env-host:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "envkey")
    monkeypatch.setenv("MINIO_SECRET_KEY", "envsecret")
    monkeypatch.setenv("MINIO_BUCKET", "envbucket")
    settings = sb.settings_from("minio", {})
    assert settings.endpoint == "env-host:9000"
    assert settings.access_key == "envkey"
    assert settings.secret_key == "envsecret"
    assert settings.bucket == "envbucket"
    # No per-workspace overrides -> may reuse get_minio_client.
    assert settings.from_env is True


def test_settings_from_s3_reads_config():
    cfg = {
        "endpoint": "s3.example.com",
        "region": "us-west-2",
        "bucket": "mybucket",
        "access_key": "AK",
        "secret_key": "SK",
        "secure": True,
    }
    settings = sb.settings_from("s3", cfg)
    assert settings.backend == "s3"
    assert settings.region == "us-west-2"
    assert settings.bucket == "mybucket"
    assert settings.from_env is False


def test_public_config_redacts_secret():
    settings = sb.settings_from("s3", {"secret_key": "topsecret", "access_key": "AK"})
    pub = sb.public_config(settings)
    assert pub["secret_key"] is None
    assert pub["secret_key_set"] is True
    assert pub["access_key"] == "AK"
    assert "topsecret" not in json.dumps(pub)


def test_normalize_s3_endpoint_adds_scheme():
    assert sb._normalize_s3_endpoint("host:9000", False) == "http://host:9000"
    assert sb._normalize_s3_endpoint("host:9000", True) == "https://host:9000"
    assert sb._normalize_s3_endpoint("https://host", False) == "https://host"


def test_resolve_workspace_storage_reads_backend_and_config(monkeypatch):
    monkeypatch.setenv("MINIO_DISABLED", "true")
    with TestingSessionLocal() as db:
        ws = Workspace(
            id=str(uuid.uuid4()),
            name="WS",
            created_by="seed",
            storage_backend="s3",
            storage_config=json.dumps({"bucket": "resolved-bucket", "region": "eu-1"}),
        )
        db.add(ws)
        db.commit()
        settings = sb.resolve_workspace_storage(db, ws.id)
    assert settings.backend == "s3"
    assert settings.bucket == "resolved-bucket"
    assert settings.region == "eu-1"


def test_resolve_workspace_storage_missing_workspace_defaults_to_minio():
    with TestingSessionLocal() as db:
        settings = sb.resolve_workspace_storage(db, "does-not-exist")
    assert settings.backend == "minio"


def test_test_connection_reports_failure_gracefully(monkeypatch):
    def _boom(_settings):
        raise RuntimeError("unreachable")

    monkeypatch.setattr(sb, "get_client", _boom)
    ok, detail = sb.test_connection(sb.settings_from("s3", {"bucket": "b"}))
    assert ok is False
    assert "unreachable" in detail


# ---------------------------------------------------------------------------
# storage.presign_put_url routing
# ---------------------------------------------------------------------------


def test_presign_put_url_without_workspace_is_backward_compatible(monkeypatch):
    monkeypatch.setenv("MINIO_DISABLED", "true")
    monkeypatch.setenv("S3_BUCKET", "visionforge")
    out = storage.presign_put_url("ver-1", "img.jpg")
    assert out["fields"] == {}
    assert out["url"].endswith("visionforge/datasets/ver-1/img.jpg")


def test_presign_put_url_routes_through_workspace_bucket(monkeypatch):
    monkeypatch.setenv("MINIO_DISABLED", "true")
    with TestingSessionLocal() as db:
        ws = Workspace(
            id=str(uuid.uuid4()),
            name="WS",
            created_by="seed",
            storage_backend="s3",
            storage_config=json.dumps({"bucket": "ws-bucket"}),
        )
        db.add(ws)
        db.commit()
        out = storage.presign_put_url("ver-9", "a.jpg", workspace_id=ws.id, db=db)
    assert out["url"].endswith("ws-bucket/datasets/ver-9/a.jpg")


# ---------------------------------------------------------------------------
# API: api/settings
# ---------------------------------------------------------------------------


@pytest.fixture
def owner_workspace():
    """Create a user + workspace they own, and override auth to that user."""
    user_id = f"storage-owner-{uuid.uuid4().hex[:8]}"
    with TestingSessionLocal() as db:
        user = User(id=user_id, email=f"{user_id}@ex.com", name="Owner", password_hash="x")
        db.add(user)
        ws = Workspace(id=str(uuid.uuid4()), name="Storage WS", created_by=user_id)
        db.add(ws)
        db.commit()
        ws_id = ws.id

    def _override() -> User:
        return User(id=user_id, email=f"{user_id}@ex.com", name="Owner", password_hash="x")

    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _override
    try:
        yield ws_id
    finally:
        if prev is not None:
            app.dependency_overrides[get_current_user] = prev
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_get_storage_defaults_to_minio(owner_workspace):
    r = client.get(f"/api/settings/workspaces/{owner_workspace}/storage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backend"] == "minio"
    assert "secret_key" in body["config"]
    assert body["config"]["secret_key"] is None


def test_put_rejects_invalid_backend(owner_workspace):
    r = client.put(
        f"/api/settings/workspaces/{owner_workspace}/storage",
        json={"backend": "azure", "config": {}},
    )
    assert r.status_code == 422, r.text


def test_put_persists_and_redacts_and_preserves_secret(owner_workspace):
    # First write: full s3 config including a secret.
    r = client.put(
        f"/api/settings/workspaces/{owner_workspace}/storage",
        json={
            "backend": "s3",
            "config": {
                "endpoint": "s3.example.com",
                "region": "us-east-1",
                "bucket": "team-bucket",
                "access_key": "AKIA",
                "secret_key": "supersecret",
                "secure": True,
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backend"] == "s3"
    assert body["config"]["bucket"] == "team-bucket"
    assert body["config"]["secret_key"] is None  # never echoed
    assert body["config"]["secret_key_set"] is True

    # The stored secret must be persisted verbatim (not redacted) in the DB.
    with TestingSessionLocal() as db:
        ws = db.get(Workspace, owner_workspace)
        assert json.loads(ws.storage_config)["secret_key"] == "supersecret"

    # Second write omits secret_key -> stored secret must be preserved.
    r2 = client.put(
        f"/api/settings/workspaces/{owner_workspace}/storage",
        json={"backend": "s3", "config": {"bucket": "renamed-bucket"}},
    )
    assert r2.status_code == 200, r2.text
    with TestingSessionLocal() as db:
        ws = db.get(Workspace, owner_workspace)
        stored = json.loads(ws.storage_config)
        assert stored["bucket"] == "renamed-bucket"
        assert stored["secret_key"] == "supersecret"


def test_test_endpoint_returns_ok_and_detail(owner_workspace, monkeypatch):
    monkeypatch.setattr(sb, "test_connection", lambda s: (True, "all good"))
    r = client.post(
        f"/api/settings/workspaces/{owner_workspace}/storage/test",
        json={"backend": "minio", "config": {"bucket": "b"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["detail"] == "all good"


def test_storage_access_denied_for_non_member():
    """A user with no membership and no ownership is rejected (403)."""
    other_id = f"outsider-{uuid.uuid4().hex[:8]}"
    with TestingSessionLocal() as db:
        owner = User(id=f"o-{uuid.uuid4().hex[:6]}", email="o@ex.com", name="O", password_hash="x")
        db.add(owner)
        ws = Workspace(id=str(uuid.uuid4()), name="Private", created_by=owner.id)
        db.add(ws)
        db.commit()
        ws_id = ws.id

    def _override() -> User:
        return User(id=other_id, email=f"{other_id}@ex.com", name="X", password_hash="x")

    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _override
    try:
        r = client.get(f"/api/settings/workspaces/{ws_id}/storage")
        assert r.status_code == 403, r.text
    finally:
        if prev is not None:
            app.dependency_overrides[get_current_user] = prev
        else:
            app.dependency_overrides.pop(get_current_user, None)
