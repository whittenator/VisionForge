"""Contract tests for the training capabilities API."""

from fastapi.testclient import TestClient

from app.db.deps import get_current_user
from app.main import app
from app.models.user import User

# Auth is bearer-token based; bypass it with a stub user for these read-only tests.
app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="t@t.io", name="t")
client = TestClient(app)


def test_list_frameworks_returns_capabilities():
    r = client.get("/api/training/frameworks")
    assert r.status_code == 200
    items = r.json()["items"]
    keys = {item["key"] for item in items}
    assert {"ultralytics", "timm"} <= keys
    timm = next(i for i in items if i["key"] == "timm")
    assert timm["supported_tasks"] == ["classify"]
    assert any(g["title"] == "Architecture" for g in timm["groups"])


def test_search_models_unknown_framework_404():
    r = client.get("/api/training/frameworks/nope/models")
    assert r.status_code == 404


def test_search_models_ultralytics_filter():
    r = client.get("/api/training/frameworks/ultralytics/models?task=detect&query=yolov8s")
    assert r.status_code == 200
    assert r.json()["items"] == ["yolov8s.pt"]
