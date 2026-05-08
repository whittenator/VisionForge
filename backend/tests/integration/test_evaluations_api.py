"""Integration tests for /api/evaluations.

We bypass `get_current_user` for these tests so the focus stays on evaluation
behavior, mirroring the cluster integration tests.
"""

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


def _u(p: str) -> str:
    return f"{p}-{uuid.uuid4().hex[:8]}"


def test_evaluation_with_unknown_artifact_returns_400():
    r = client.post(
        "/api/evaluations",
        json={
            "artifact_id": "missing",
            "dataset_version_id": "missing-too",
        },
    )
    assert r.status_code == 400


def test_create_evaluation_returns_job():
    # Create a project, dataset, version, and artifact directly via the ORM
    from app.db.session import SessionLocal
    from app.models.artifact import ModelArtifact
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.project import Project
    from app.models.user import User as UserModel
    from app.models.workspace import Workspace

    artifact_id: str
    version_id: str
    with SessionLocal() as db:
        # Ensure the fake current user exists for downstream FKs
        if not db.get(UserModel, "test-user"):
            db.add(UserModel(id="test-user", email="t@x.com", name="Tester", password_hash="$2b$x"))
            db.commit()
        ws = Workspace(id=_u("ws"), name="W", region="us", created_by="test-user")
        db.add(ws)
        db.commit()
        proj_id = _u("proj")
        proj = Project(id=proj_id, workspace_id=ws.id, name="P", slug=proj_id)
        db.add(proj)
        db.commit()
        ds = Dataset(id=_u("ds"), project_id=proj_id, name="D", description="")
        db.add(ds)
        db.commit()
        version_id = _u("v")
        v = DatasetVersion(id=version_id, dataset_id=ds.id, version=1)
        db.add(v)
        db.commit()
        artifact_id = _u("a")
        art = ModelArtifact(
            id=artifact_id,
            project_id=proj_id,
            run_id=None,
            name="m",
            version="1",
            type="yolo",
            format="pytorch",
            storage_path="datasets/x/y.pt",
        )
        db.add(art)
        db.commit()

    r = client.post(
        "/api/evaluations",
        json={
            "artifact_id": artifact_id,
            "dataset_version_id": version_id,
            "split": "test",
            "iou_threshold": 0.5,
            "score_threshold": 0.25,
            "sample_fpfn_count": 10,
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["type"] == "evaluation"
    assert body["status"] == "queued"


def test_get_unknown_evaluation_404():
    r = client.get("/api/evaluations/does-not-exist")
    assert r.status_code == 404
