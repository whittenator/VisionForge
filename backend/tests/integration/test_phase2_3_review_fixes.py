"""Regression tests for the Copilot-review issues addressed in PR #11.

Covers:
* fps_interval validation on the frame-extraction trigger
* mAP50 invariance and mAP_at_iou for non-default thresholds (unit-side)
* Wizard atomicity: a failed class map must roll back the project + dataset
"""

from __future__ import annotations

import uuid
from unittest import mock

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


def _seed_video_asset() -> tuple[str, str]:
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
        db.add(Dataset(id=ds_id, project_id=proj_id, name="D"))
        ver_id = _u("v")
        db.add(DatasetVersion(id=ver_id, dataset_id=ds_id, version=1))
        asset_id = _u("a")
        db.add(
            Asset(
                id=asset_id,
                dataset_id=ds_id,
                version_id=ver_id,
                uri=f"datasets/{ver_id}/clip.mp4",
                mime_type="video/mp4",
                label_status="unlabeled",
            )
        )
        db.commit()
        return ds_id, asset_id


def test_extract_frames_rejects_zero_fps_interval():
    ds_id, asset_id = _seed_video_asset()
    r = client.post(
        f"/api/datasets/{ds_id}/assets/{asset_id}/extract-frames?fps_interval=0",
    )
    assert r.status_code == 422  # FastAPI validation


def test_extract_frames_rejects_negative_fps_interval():
    ds_id, asset_id = _seed_video_asset()
    r = client.post(
        f"/api/datasets/{ds_id}/assets/{asset_id}/extract-frames?fps_interval=-1",
    )
    assert r.status_code == 422


def test_wizard_rolls_back_project_when_class_map_fails():
    """If ClassMap creation explodes mid-wizard, we must not leak a project.

    We patch ClassMap to raise on construction. The wizard should rollback,
    so the project name must NOT be findable after the failed call.
    """
    from app.models import dataset as dataset_models

    name = f"rollback-{uuid.uuid4().hex[:8]}"
    real_cm = dataset_models.ClassMap

    class _Boom(real_cm):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("simulated class-map failure")

    with mock.patch.object(dataset_models, "ClassMap", _Boom):
        r = client.post(
            "/api/projects/wizard",
            json={
                "name": name,
                "task_type": "detect",
                "dataset_name": "default",
                "classes": [{"name": "person"}],
            },
        )
        # The endpoint propagates the failure as 500.
        assert r.status_code in (500, 400)

    # Project must not exist — the wizard rolled back.
    listing = client.get("/api/projects?page=1&page_size=200").json()
    names = [p["name"] for p in listing["items"]]
    assert name not in names, f"wizard leaked a partial project: {name}"


def test_extract_frames_dispatch_failure_marks_failed():
    """Broker outage on extract-frames should fail the job, not leave it queued."""
    from app.db.session import SessionLocal
    from app.models.job import Job

    ds_id, asset_id = _seed_video_asset()

    with mock.patch(
        "app.jobs.celery_app.celery_app.send_task",
        side_effect=RuntimeError("broker unreachable"),
    ):
        r = client.post(
            f"/api/datasets/{ds_id}/assets/{asset_id}/extract-frames?fps_interval=1.0",
        )
    assert r.status_code == 503

    with SessionLocal() as db:
        job = (
            db.query(Job)
            .filter(Job.type == "frame_extraction")
            .order_by(Job.created_at.desc())
            .first()
        )
        assert job is not None
        assert job.status == "failed"
