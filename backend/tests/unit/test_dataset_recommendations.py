"""Unit tests for dataset_recommendations_service.generate_recommendations."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


def _register_models() -> None:
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


def _ids(recs):
    return {r["id"] for r in recs}


def test_empty_dataset_returns_no_recommendations(db):
    from app.services.dataset_recommendations_service import generate_recommendations

    ds, _ = _seed_dataset(db)
    assert generate_recommendations(db, ds.id) == []


def test_missing_dataset_returns_empty(db):
    from app.services.dataset_recommendations_service import generate_recommendations

    assert generate_recommendations(db, "does-not-exist") == []


def test_imbalance_and_coverage_recommendations(db):
    from app.services.dataset_recommendations_service import generate_recommendations

    ds, ver = _seed_dataset(db)

    # One labeled image with 20 'cat' instances vs 1 'dog' -> 20x imbalance (high).
    a1 = _seed_asset(db, ds, ver, label_status="labeled", width=800, height=600)
    for _ in range(20):
        _seed_annotation(db, a1, class_name="cat")
    a2 = _seed_asset(db, ds, ver, label_status="labeled", width=800, height=600)
    _seed_annotation(db, a2, class_name="dog")

    # Many unlabeled images -> low coverage (>50% unlabeled) high severity.
    for _ in range(8):
        _seed_asset(db, ds, ver, label_status="unlabeled", width=800, height=600)

    recs = generate_recommendations(db, ds.id)
    ids = _ids(recs)

    assert "class_imbalance" in ids
    assert "low_coverage" in ids
    # Small dataset (labeled < 100) and empty images also expected.
    assert "small_dataset" in ids

    imbalance = next(r for r in recs if r["id"] == "class_imbalance")
    assert imbalance["severity"] == "high"
    assert imbalance["metric"] >= 10
    # over/under-represented classes named
    assert "cat" in imbalance["detail"] and "dog" in imbalance["detail"]

    coverage = next(r for r in recs if r["id"] == "low_coverage")
    assert coverage["severity"] == "high"

    # Sorted by severity: high first, low last.
    order = {"high": 0, "medium": 1, "low": 2}
    sev_values = [order[r["severity"]] for r in recs]
    assert sev_values == sorted(sev_values)


def test_unused_classes_recommendation(db):
    from app.models.dataset import ClassMap
    from app.services.dataset_recommendations_service import generate_recommendations

    ds, ver = _seed_dataset(db)
    cm = ClassMap(id="cm-1", project_id="proj-1", classes=json.dumps(["cat", "dog", "bird"]))
    db.add(cm)
    ds.class_map_id = "cm-1"
    db.add(ds)
    db.commit()

    a1 = _seed_asset(db, ds, ver, label_status="labeled", width=640, height=480)
    _seed_annotation(db, a1, class_name="cat")

    recs = generate_recommendations(db, ds.id)
    unused = next((r for r in recs if r["id"] == "unused_classes"), None)
    assert unused is not None
    assert unused["severity"] == "medium"
    assert "dog" in unused["detail"] and "bird" in unused["detail"]


def test_endpoint_via_testclient(db):
    """The API endpoint returns the recommendations envelope with Role.VIEWER."""
    from app.db.deps import get_current_user
    from app.main import app
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.user import User
    from tests.conftest import TestingSessionLocal, client, ensure_project

    app.dependency_overrides[get_current_user] = lambda: User(
        id="rec-tester", email="rec@example.com", name="T", password_hash="x"
    )

    ensure_project("p")
    # Seed via the shared app session so the endpoint (its own session) sees it.
    with TestingSessionLocal() as s:
        ds = Dataset(id="ds-rec", project_id="p", name="RecDS")
        s.add(ds)
        ver = DatasetVersion(id="ver-rec", dataset_id="ds-rec", version=1)
        s.add(ver)
        s.commit()
        _ASSET_SEQ[0] += 100
        from app.models.annotation import Annotation
        from app.models.asset import Asset

        a = Asset(
            id="asset-rec-1",
            dataset_id="ds-rec",
            version_id="ver-rec",
            uri="x.jpg",
            mime_type="image/jpeg",
            label_status="labeled",
            width=800,
            height=600,
        )
        s.add(a)
        s.commit()
        for i in range(15):
            s.add(
                Annotation(
                    id=f"ann-rec-{i}",
                    asset_id="asset-rec-1",
                    type="box",
                    geometry=json.dumps({"x": 0, "y": 0, "w": 10, "h": 10}),
                    class_name="cat",
                    author_id="user-1",
                )
            )
        s.commit()

    resp = client.get("/api/datasets/ds-rec/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["generated_from_version"] is None
    assert isinstance(body["items"], list)
