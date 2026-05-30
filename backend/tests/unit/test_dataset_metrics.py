"""Unit tests for asset_service.get_dataset_metrics using SQLite in-memory DB."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


def _register_models() -> None:
    """Import the ORM models so their tables register on Base.metadata before
    create_all (the app conftest does this transitively; we do it explicitly so
    the suite also runs standalone)."""
    import app.models.annotation  # noqa: F401
    import app.models.asset  # noqa: F401
    import app.models.dataset  # noqa: F401
    import app.models.dataset_version  # noqa: F401
    import app.models.project  # noqa: F401
    import app.models.workspace  # noqa: F401


@pytest.fixture
def db():
    _register_models()
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _seed_dataset(db, dataset_id="ds-1"):
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.project import Project
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="WS", created_by="user-1"))
    db.add(Project(id="proj-1", workspace_id="ws-1", name="P", slug="p"))
    ds = Dataset(id=dataset_id, project_id="proj-1", name="DS")
    db.add(ds)
    ver = DatasetVersion(id="ver-1", dataset_id=dataset_id, version=1)
    db.add(ver)
    db.commit()
    return ds, ver


_ASSET_SEQ = [0]


def _seed_asset(db, ds, ver, *, label_status="unlabeled", width=None, height=None):
    from app.models.asset import Asset

    _ASSET_SEQ[0] += 1
    aid = f"asset-{_ASSET_SEQ[0]}"
    a = Asset(
        id=aid,
        dataset_id=ds.id,
        version_id=ver.id,
        uri=f"datasets/v1/{aid}.jpg",
        mime_type="image/jpeg",
        label_status=label_status,
        width=width,
        height=height,
    )
    db.add(a)
    db.commit()
    return a


_ANN_SEQ = [0]


def _seed_annotation(db, asset, *, class_name="cat", geometry=None, ann_type="box"):
    from app.models.annotation import Annotation

    _ANN_SEQ[0] += 1
    geom = geometry or json.dumps({"x": 0, "y": 0, "w": 10, "h": 10})
    ann = Annotation(
        id=f"ann-{_ANN_SEQ[0]}",
        asset_id=asset.id,
        type=ann_type,
        geometry=geom,
        class_name=class_name,
        author_id="user-1",
    )
    db.add(ann)
    db.commit()
    return ann


def test_get_dataset_metrics(db):
    from app.services import asset_service

    ds, ver = _seed_dataset(db)
    # a1: labeled, 3 small cat boxes, with dimensions
    a1 = _seed_asset(db, ds, ver, label_status="labeled", width=800, height=600)
    for _ in range(3):
        _seed_annotation(db, a1, class_name="cat")
    # a2: labeled, 1 large dog box
    a2 = _seed_asset(db, ds, ver, label_status="labeled", width=1920, height=1080)
    _seed_annotation(
        db, a2, class_name="dog", geometry=json.dumps({"x": 0, "y": 0, "w": 200, "h": 200})
    )
    # a3: empty image (no annotations)
    _seed_asset(db, ds, ver, label_status="unlabeled", width=400, height=300)

    m = asset_service.get_dataset_metrics(db, ds.id)

    assert m["total_assets"] == 3
    assert m["total_annotations"] == 4
    assert m["empty_images"] == 1
    assert m["class_balance"]["instances"]["cat"] == 3
    assert m["class_balance"]["instances"]["dog"] == 1
    assert m["class_balance"]["images"]["cat"] == 1
    assert m["class_balance"]["imbalance_ratio"] == 3.0
    assert m["per_image"]["histogram"]["0"] == 1
    assert m["per_image"]["histogram"]["1"] == 1
    assert m["per_image"]["histogram"]["2-5"] == 1
    assert m["per_image"]["max"] == 3
    assert m["box_geometry"]["area_histogram"]["small (<32²)"] == 3
    assert m["box_geometry"]["area_histogram"]["large (≥96²)"] == 1
    assert m["box_geometry"]["sampled"] is False
    assert m["resolution"]["with_dimensions"] == 3
    assert m["resolution"]["histogram"]["≥1920"] == 1


def test_get_dataset_metrics_empty(db):
    from app.services import asset_service

    ds, _ = _seed_dataset(db)
    m = asset_service.get_dataset_metrics(db, ds.id)
    assert m["total_assets"] == 0
    assert m["total_annotations"] == 0
    assert m["coverage_pct"] == 0.0
    assert m["class_balance"]["imbalance_ratio"] is None


def test_get_dataset_metrics_unused_classes(db):
    from app.models.dataset import ClassMap
    from app.services import asset_service

    ds, ver = _seed_dataset(db)
    cm = ClassMap(id="cm-1", project_id="proj-1", classes=json.dumps(["cat", "dog", "bird"]))
    db.add(cm)
    ds.class_map_id = "cm-1"
    db.add(ds)
    db.commit()
    a1 = _seed_asset(db, ds, ver, label_status="labeled", width=640, height=480)
    _seed_annotation(db, a1, class_name="cat")

    m = asset_service.get_dataset_metrics(db, ds.id)
    assert set(m["class_balance"]["unused_classes"]) == {"dog", "bird"}
