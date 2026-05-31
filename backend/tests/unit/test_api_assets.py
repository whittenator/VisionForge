"""Request-level tests for the assets router (``api/assets.py``).

The router previously had no direct tests. We seed datasets/versions/assets
through the test session and exercise the read endpoints, the neighbor cursor
logic, and the upload-confirm write path. Auth is satisfied with a fake user;
``MINIO_DISABLED`` keeps presign best-effort.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db.deps import get_current_user
from app.main import app
from app.models.asset import Asset
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.user import User
from tests.conftest import TestingSessionLocal, client


def _fake_user() -> User:
    return User(id="asset-tester", email="assets@example.com", name="T", password_hash="x")


app.dependency_overrides[get_current_user] = _fake_user


def _seed_assets(n: int) -> tuple[str, str, list[str]]:
    db = TestingSessionLocal()
    try:
        ds = Dataset(id=str(uuid.uuid4()), project_id="p", name="ds")
        db.add(ds)
        db.commit()
        ver = DatasetVersion(id=str(uuid.uuid4()), dataset_id=ds.id, version=1)
        db.add(ver)
        db.commit()
        ids = []
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(n):
            a = Asset(
                id=str(uuid.uuid4()),
                dataset_id=ds.id,
                version_id=ver.id,
                uri=f"datasets/{ver.id}/img{i}.jpg",
                mime_type="image/jpeg",
                label_status="unlabelled" if i % 2 else "labeled",
                # Distinct, increasing timestamps so the (created_at, id) cursor
                # ordering in /neighbors is deterministic.
                created_at=base + timedelta(seconds=i),
            )
            db.add(a)
            ids.append(a.id)
        db.commit()
        return ds.id, ver.id, ids
    finally:
        db.close()


def test_get_asset_404_when_missing():
    r = client.get("/api/assets/does-not-exist")
    assert r.status_code == 404


def test_get_asset_returns_fields():
    _, _, ids = _seed_assets(1)
    r = client.get(f"/api/assets/{ids[0]}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == ids[0]
    assert body["mime_type"] == "image/jpeg"
    assert "download_url" in body


def test_list_dataset_assets_pagination_shape():
    ds_id, ver_id, _ = _seed_assets(5)
    r = client.get(f"/api/datasets/{ds_id}/assets?limit=2&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 0


def test_list_dataset_assets_label_status_filter():
    ds_id, _, _ = _seed_assets(4)  # 2 labeled, 2 unlabelled
    r = client.get(f"/api/datasets/{ds_id}/assets?label_status=labeled")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(item["label_status"] == "labeled" for item in body["items"])


def test_asset_neighbors_prev_next_index():
    ds_id, ver_id, ids = _seed_assets(3)
    # Ordering is (created_at, id), which need not match insertion order, so
    # assert the invariants across all three: total is 3 everywhere, exactly one
    # has no prev (the first) and exactly one has no next (the last).
    bodies = []
    for aid in ids:
        r = client.get(f"/api/assets/{aid}/neighbors")
        assert r.status_code == 200
        bodies.append(r.json())

    assert all(b["total"] == 3 for b in bodies)
    assert sum(1 for b in bodies if b["prev"] is None) == 1
    assert sum(1 for b in bodies if b["next"] is None) == 1
    assert sorted(b["index"] for b in bodies) == [0, 1, 2]


def test_asset_neighbors_404_when_missing():
    assert client.get("/api/assets/missing/neighbors").status_code == 404


def test_confirm_upload_creates_asset():
    ds_id, ver_id, _ = _seed_assets(0)
    r = client.post(
        "/api/ingest/confirm",
        json={
            "dataset_id": ds_id,
            "version_id": ver_id,
            "storage_key": f"datasets/{ver_id}/new.jpg",
            "filename": "new.jpg",
            "content_type": "image/jpeg",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["dataset_id"] == ds_id
