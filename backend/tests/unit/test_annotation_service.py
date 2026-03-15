"""Unit tests for annotation service using SQLite in-memory DB."""
from __future__ import annotations

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_asset(db, dataset_id: str = "ds-1") -> str:
    from app.models.asset import Asset
    from app.models.workspace import Workspace
    from app.models.project import Project
    from app.models.dataset import Dataset

    ws = Workspace(id="ws-1", name="Test WS", created_by="user-1")
    db.add(ws)
    proj = Project(id="proj-1", workspace_id="ws-1", name="Test", slug="test")
    db.add(proj)
    ds = Dataset(id=dataset_id, project_id="proj-1", name="DS")
    db.add(ds)
    asset = Asset(id="asset-1", dataset_id=dataset_id, uri="datasets/v1/img.jpg",
                  mime_type="image/jpeg", label_status="unlabeled")
    db.add(asset)
    db.commit()
    return "asset-1"


def test_create_annotation(db):
    from app.services.annotation_service import create_annotation
    asset_id = _make_asset(db)
    from app.models.user import User
    user = User(id="user-1", name="Tester", email="t@t.com")
    db.add(user)
    db.commit()

    ann = create_annotation(
        db,
        asset_id=asset_id,
        author_id="user-1",
        type="box",
        geometry={"x": 10, "y": 20, "w": 50, "h": 40},
        class_name="cat",
    )
    assert ann.id
    assert ann.class_name == "cat"
    assert ann.type == "box"
    assert json.loads(ann.geometry) == {"x": 10, "y": 20, "w": 50, "h": 40}


def test_update_annotation_stores_history(db):
    from app.services.annotation_service import create_annotation, update_annotation
    _make_asset(db)
    from app.models.user import User
    db.add(User(id="user-1", name="T", email="t@t.com"))
    db.commit()

    ann = create_annotation(db, asset_id="asset-1", author_id="user-1",
                             type="box", geometry={"x": 0, "y": 0, "w": 10, "h": 10},
                             class_name="dog")
    updated = update_annotation(db, ann.id, geometry={"x": 5, "y": 5, "w": 20, "h": 20},
                                class_name="cat")
    assert updated is not None
    assert updated.class_name == "cat"
    history = json.loads(updated.history)
    assert len(history) == 1
    assert json.loads(history[0]["geometry"]) == {"x": 0, "y": 0, "w": 10, "h": 10}


def test_delete_annotation(db):
    from app.services.annotation_service import create_annotation, delete_annotation, get_asset_annotations
    _make_asset(db)
    from app.models.user import User
    db.add(User(id="user-1", name="T", email="t@t.com"))
    db.commit()

    ann = create_annotation(db, asset_id="asset-1", author_id="user-1",
                             type="classification", geometry={"class": "cat"},
                             class_name="cat")
    assert len(get_asset_annotations(db, "asset-1")) == 1
    result = delete_annotation(db, ann.id)
    assert result is True
    assert len(get_asset_annotations(db, "asset-1")) == 0
