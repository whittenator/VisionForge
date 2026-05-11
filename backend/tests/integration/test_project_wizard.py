"""Integration tests for the multi-step project wizard endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.deps import get_current_user
from app.main import app
from app.models.user import User


def _fake_user() -> User:
    return User(id="test-user", email="t@x.com", name="Tester", password_hash="$2b$x")


app.dependency_overrides[get_current_user] = _fake_user
client = TestClient(app)


def test_wizard_creates_project_dataset_and_class_map():
    r = client.post(
        "/api/projects/wizard",
        json={
            "name": "Wizard Detector",
            "description": "Auto-created via wizard",
            "task_type": "detect",
            "dataset_name": "default",
            "classes": [
                {"name": "person"},
                {"name": "car"},
                {"name": "dog"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project"]["task_type"] == "detect"
    assert body["dataset"]["task_type"] == "detect"
    assert body["version"]["version"] == 1
    assert sorted(body["classes"]) == ["car", "dog", "person"]


def test_wizard_rejects_unknown_task_type():
    r = client.post(
        "/api/projects/wizard",
        json={
            "name": "X",
            "task_type": "segmentation",  # not in VALID_TASK_TYPES
            "dataset_name": "default",
            "classes": [],
        },
    )
    assert r.status_code == 400


def test_paginated_projects_response_shape():
    # The list endpoint now returns {items, total, page, page_size}.
    r = client.get("/api/projects?page=1&page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
