"""Service-level performance guards for annotation + upload-presign hot paths.

The HTTP-level perf tests (`test_api_perf.py`) cover end-to-end latency, but they
require a working auth chain. These guards bypass the API and exercise the
service layer directly so they remain useful even when auth is misconfigured in
the test environment, and they pin the budgets called out in
`specs/003-visionforge-web-revamp/quickstart.md` ("annotation actions < 100ms").
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(int(len(s) * 0.95) - 1, len(s) - 1))
    return s[idx]


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _seed(db) -> str:
    from app.models.asset import Asset
    from app.models.dataset import Dataset
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws", name="WS", created_by="u"))
    db.add(Project(id="p", workspace_id="ws", name="P", slug="p"))
    db.add(Dataset(id="d", project_id="p", name="D"))
    db.add(User(id="u", name="U", email="u@u.com"))
    db.add(
        Asset(
            id="a",
            dataset_id="d",
            uri="datasets/d/img.jpg",
            mime_type="image/jpeg",
            label_status="unlabeled",
        )
    )
    db.commit()
    return "a"


def test_annotation_create_p95_under_100ms(db):
    from app.services.annotation_service import create_annotation

    asset_id = _seed(db)
    # Warmup
    create_annotation(
        db,
        asset_id=asset_id,
        author_id="u",
        type="box",
        geometry={"x": 0, "y": 0, "w": 1, "h": 1},
        class_name="warm",
    )

    latencies: list[float] = []
    for i in range(30):
        t0 = time.perf_counter()
        create_annotation(
            db,
            asset_id=asset_id,
            author_id="u",
            type="box",
            geometry={"x": i, "y": i, "w": 10, "h": 10},
            class_name=f"c{i}",
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)

    p95 = _p95(latencies)
    assert p95 < 100.0, f"annotation create p95 too high: {p95:.2f}ms"


def test_annotation_update_p95_under_100ms(db):
    from app.services.annotation_service import create_annotation, update_annotation

    asset_id = _seed(db)
    ann = create_annotation(
        db,
        asset_id=asset_id,
        author_id="u",
        type="box",
        geometry={"x": 0, "y": 0, "w": 1, "h": 1},
        class_name="initial",
    )

    latencies: list[float] = []
    for i in range(30):
        t0 = time.perf_counter()
        update_annotation(
            db,
            ann.id,
            geometry={"x": i, "y": i, "w": 5, "h": 5},
            class_name=f"c{i}",
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)

    p95 = _p95(latencies)
    assert p95 < 100.0, f"annotation update p95 too high: {p95:.2f}ms"


def test_upload_presign_p95_under_50ms(monkeypatch):
    """Presigning a single upload URL should be cheap when storage is mocked."""
    monkeypatch.setenv("MINIO_DISABLED", "true")
    from app.services.ingest_service import get_presigned_upload

    # Warmup
    get_presigned_upload("ver-1", "warm.bin", "application/octet-stream")

    latencies: list[float] = []
    for i in range(50):
        t0 = time.perf_counter()
        result = get_presigned_upload("ver-1", f"f-{i}.bin", "application/octet-stream")
        latencies.append((time.perf_counter() - t0) * 1000.0)
        assert "url" in result
        assert result["objectKey"].endswith(f"f-{i}.bin")

    p95 = _p95(latencies)
    assert p95 < 50.0, f"upload-presign p95 too high: {p95:.2f}ms"
