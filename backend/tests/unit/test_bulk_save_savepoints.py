"""Verify bulk_save uses savepoints + a single commit (not O(n) commits)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
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


def _seed(db) -> str:
    from app.models.asset import Asset
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="W", created_by="user-1"))
    db.add(Project(id="p-1", workspace_id="ws-1", name="P", slug="p"))
    db.add(Dataset(id="d-1", project_id="p-1", name="D"))
    db.add(DatasetVersion(id="v-1", dataset_id="d-1", version=1))
    db.add(
        Asset(
            id="a-1",
            dataset_id="d-1",
            version_id="v-1",
            uri="datasets/v1/img.jpg",
            mime_type="image/jpeg",
            label_status="unlabeled",
        )
    )
    db.add(User(id="user-1", name="A", email="a@a.com"))
    db.commit()
    return "a-1"


def test_bulk_save_emits_a_single_outer_commit(db):
    """Multiple creates + updates should not cause O(n) outer commits."""
    from app.services.annotation_service import bulk_save

    asset_id = _seed(db)
    engine = db.get_bind()
    commit_count = {"n": 0}

    @event.listens_for(engine, "commit")
    def _on_commit(_conn):
        commit_count["n"] += 1

    bulk_save(
        db,
        author_id="user-1",
        creates=[
            {
                "client_id": f"tmp-{i}",
                "asset_id": asset_id,
                "type": "box",
                "geometry": {"x": i, "y": i, "w": 5, "h": 5},
                "class_name": "cat",
            }
            for i in range(5)
        ],
        updates=[],
        deletes=[],
    )

    # The exact count depends on SQLAlchemy bookkeeping, but it must be a
    # small constant — emphatically not 5 (one per create).
    assert commit_count["n"] <= 2, f"too many commits: {commit_count['n']}"


def test_bulk_save_failed_row_does_not_block_rest(db):
    """A bad geometry should fail just that row; the rest should land."""
    from app.services.annotation_service import bulk_save, get_asset_annotations

    asset_id = _seed(db)
    result = bulk_save(
        db,
        author_id="user-1",
        creates=[
            {
                "client_id": "good",
                "asset_id": asset_id,
                "type": "box",
                "geometry": {"x": 0, "y": 0, "w": 10, "h": 10},
                "class_name": "cat",
            },
            {
                "client_id": "bad",
                "asset_id": asset_id,
                "type": "box",
                "geometry": {"x": 0, "y": 0, "w": 0, "h": 0},  # invalid
                "class_name": "cat",
            },
            {
                "client_id": "also-good",
                "asset_id": asset_id,
                "type": "box",
                "geometry": {"x": 5, "y": 5, "w": 5, "h": 5},
                "class_name": "dog",
            },
        ],
        updates=[],
        deletes=[],
    )
    statuses = [c["status"] for c in result["created"]]
    assert statuses == ["ok", "error", "ok"]
    rows = get_asset_annotations(db, asset_id)
    assert len(rows) == 2
