"""Integration tests for the Phase 2 annotation endpoints (bulk, review)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.db.deps import get_current_user
from app.main import app
from app.models.user import User


def _fake_user() -> User:
    return User(id="test-user", email="t@x.com", name="Tester", password_hash="$2b$x")


app.dependency_overrides[get_current_user] = _fake_user
client = TestClient(app)


def _u(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _seed_dataset_with_asset() -> tuple[str, str, str]:
    """Create a workspace/project/dataset/version/asset and return their IDs."""
    from app.db.session import SessionLocal
    from app.models.asset import Asset
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.project import Project
    from app.models.user import User as UserModel
    from app.models.workspace import Workspace

    with SessionLocal() as db:
        if not db.get(UserModel, "test-user"):
            db.add(UserModel(id="test-user", email="t@x.com", name="T", password_hash="$2b$x"))
            db.commit()
        ws_id = _u("ws")
        db.add(Workspace(id=ws_id, name="W", region="us", created_by="test-user"))
        proj_id = _u("p")
        db.add(Project(id=proj_id, workspace_id=ws_id, name="P", slug=proj_id))
        ds_id = _u("d")
        db.add(Dataset(id=ds_id, project_id=proj_id, name="D", description=""))
        ver_id = _u("v")
        db.add(DatasetVersion(id=ver_id, dataset_id=ds_id, version=1))
        asset_id = _u("a")
        db.add(
            Asset(
                id=asset_id,
                dataset_id=ds_id,
                version_id=ver_id,
                uri="datasets/x/y.jpg",
                mime_type="image/jpeg",
                label_status="unlabeled",
            )
        )
        db.commit()
        return ds_id, ver_id, asset_id


def test_bulk_save_creates_and_review_queue_summarises():
    ds_id, _ver_id, asset_id = _seed_dataset_with_asset()

    body = {
        "creates": [
            {
                "client_id": "tmp-1",
                "asset_id": asset_id,
                "type": "box",
                "geometry": {"x": 1, "y": 2, "w": 30, "h": 40},
                "class_name": "cat",
            },
            {
                "client_id": "tmp-2",
                "asset_id": asset_id,
                "type": "box",
                "geometry": {"x": 5, "y": 5, "w": 50, "h": 50},
                "class_name": "dog",
            },
        ],
        "updates": [],
        "deletes": [],
    }
    r = client.post("/api/annotations/bulk", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert len(payload["created"]) == 2
    assert all(c["status"] == "ok" for c in payload["created"])

    # Approve one, leave the other unreviewed.
    first_id = payload["created"][0]["annotation"]["id"]
    r2 = client.post(
        f"/api/annotations/{first_id}/review",
        json={"review_status": "approved"},
    )
    assert r2.status_code == 200
    assert r2.json()["review_status"] == "approved"

    # Review queue should report 1 approved + 1 unreviewed.
    summary = client.get(f"/api/annotations/datasets/{ds_id}/review/summary").json()
    assert summary["approved"] == 1
    assert summary["unreviewed"] == 1
    assert summary["rejected"] == 0
    assert summary["total"] == 2

    queue = client.get(f"/api/annotations/datasets/{ds_id}/review?review_status=unreviewed").json()
    assert queue["total"] == 1
    assert len(queue["items"]) == 1
    assert queue["items"][0]["annotation"]["review_status"] == "unreviewed"


def test_bulk_save_reports_per_row_conflict():
    _, _, asset_id = _seed_dataset_with_asset()

    # Seed an annotation by creating one via bulk.
    r = client.post(
        "/api/annotations/bulk",
        json={
            "creates": [
                {
                    "client_id": "x",
                    "asset_id": asset_id,
                    "type": "box",
                    "geometry": {"x": 0, "y": 0, "w": 5, "h": 5},
                    "class_name": "dog",
                }
            ],
            "updates": [],
            "deletes": [],
        },
    )
    ann = r.json()["created"][0]["annotation"]

    # Now send an update with a wrong expected_version → conflict.
    r2 = client.post(
        "/api/annotations/bulk",
        json={
            "creates": [],
            "updates": [
                {
                    "id": ann["id"],
                    "geometry": {"x": 1, "y": 1, "w": 6, "h": 6},
                    "expected_version": ann["version"] + 99,
                }
            ],
            "deletes": [],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["updated"][0]["status"] == "conflict"
