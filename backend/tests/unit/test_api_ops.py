"""Request-level tests for the ops router (``api/ops.py``).

Covers the system-status aggregation, the presigned upload-url endpoint, and
the frame-extraction validation/dispatch guards — none of which had direct
tests. Runs with ``MINIO_DISABLED`` so storage probes degrade gracefully.
"""

from __future__ import annotations

import uuid

from app.db.deps import get_current_user
from app.main import app
from app.models.asset import Asset
from app.models.dataset import Dataset
from app.models.user import User
from tests.conftest import TestingSessionLocal, client


def _fake_user() -> User:
    return User(id="ops-tester", email="ops@example.com", name="T", password_hash="x")


app.dependency_overrides[get_current_user] = _fake_user


def test_system_status_aggregates_components():
    r = client.get("/api/system/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded", "down")
    comps = body["components"]
    assert comps["api"]["status"] == "ok"
    # DB is the in-memory test SQLite, so it must report reachable.
    assert comps["database"]["status"] == "ok"
    assert "queue" in comps and "storage" in comps


def test_upload_url_returns_object_key():
    r = client.post(
        "/api/ingest/upload-url",
        json={
            "projectId": "p1",
            "datasetVersionId": "ver-9",
            "filename": "a.jpg",
            "contentType": "image/jpeg",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["objectKey"] == "datasets/ver-9/a.jpg"
    assert body["url"]


def _seed_asset(*, mime: str, uri: str) -> tuple[str, str]:
    db = TestingSessionLocal()
    try:
        ds = Dataset(id=str(uuid.uuid4()), project_id="p", name="ds")
        db.add(ds)
        db.commit()
        asset = Asset(
            id=str(uuid.uuid4()),
            dataset_id=ds.id,
            uri=uri,
            mime_type=mime,
            label_status="unlabelled",
        )
        db.add(asset)
        db.commit()
        return ds.id, asset.id
    finally:
        db.close()


def test_extract_frames_404_for_missing_asset():
    r = client.post("/api/datasets/d/assets/missing/extract-frames")
    assert r.status_code == 404


def test_extract_frames_rejects_non_video_asset():
    ds_id, asset_id = _seed_asset(mime="image/jpeg", uri="x/y.jpg")
    r = client.post(f"/api/datasets/{ds_id}/assets/{asset_id}/extract-frames")
    assert r.status_code == 400
    assert "not a video" in r.json()["detail"]


def test_extract_frames_rejects_mismatched_dataset():
    _, asset_id = _seed_asset(mime="video/mp4", uri="x/y.mp4")
    r = client.post(f"/api/datasets/wrong-dataset/assets/{asset_id}/extract-frames")
    assert r.status_code == 400


def test_extract_frames_rejects_invalid_interval():
    ds_id, asset_id = _seed_asset(mime="video/mp4", uri="x/y.mp4")
    r = client.post(f"/api/datasets/{ds_id}/assets/{asset_id}/extract-frames?fps_interval=0")
    assert r.status_code == 422
