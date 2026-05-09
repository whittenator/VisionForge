"""Unit tests for the Phase 2 annotation review + bulk-save additions."""

from __future__ import annotations

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


def _seed(db, dataset_id: str = "ds-1") -> str:
    from app.models.asset import Asset
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="W", created_by="user-1"))
    db.add(Project(id="proj-1", workspace_id="ws-1", name="P", slug="p"))
    db.add(Dataset(id=dataset_id, project_id="proj-1", name="DS"))
    db.add(DatasetVersion(id="ver-1", dataset_id=dataset_id, version=1))
    db.add(
        Asset(
            id="asset-1",
            dataset_id=dataset_id,
            version_id="ver-1",
            uri="datasets/v1/img.jpg",
            mime_type="image/jpeg",
            label_status="unlabeled",
        )
    )
    db.add(User(id="user-1", name="A", email="a@a.com"))
    db.add(User(id="reviewer-1", name="R", email="r@r.com"))
    db.commit()
    return "asset-1"


def test_bulk_save_creates_updates_and_deletes(db):
    from app.services.annotation_service import bulk_save, get_asset_annotations

    _seed(db)
    # Seed an existing annotation we'll update.
    from app.services.annotation_service import create_annotation

    existing = create_annotation(
        db,
        asset_id="asset-1",
        author_id="user-1",
        type="box",
        geometry={"x": 0, "y": 0, "w": 10, "h": 10},
        class_name="dog",
    )
    base_version = existing.version

    result = bulk_save(
        db,
        author_id="user-1",
        creates=[
            {
                "client_id": "tmp-1",
                "asset_id": "asset-1",
                "type": "box",
                "geometry": {"x": 5, "y": 5, "w": 20, "h": 20},
                "class_name": "cat",
            }
        ],
        updates=[
            {
                "id": existing.id,
                "geometry": {"x": 1, "y": 1, "w": 11, "h": 11},
                "class_name": "dog",
                "expected_version": existing.version,
            }
        ],
        deletes=[],
    )

    # One created, one updated, no deletes.
    assert len(result["created"]) == 1
    assert result["created"][0]["status"] == "ok"
    assert result["created"][0]["client_id"] == "tmp-1"
    assert len(result["updated"]) == 1
    assert result["updated"][0]["status"] == "ok"
    assert result["updated"][0]["annotation"]["version"] == base_version + 1

    rows = get_asset_annotations(db, "asset-1")
    assert len(rows) == 2


def test_bulk_save_reports_version_conflict(db):
    from app.services.annotation_service import bulk_save, create_annotation

    _seed(db)
    ann = create_annotation(
        db,
        asset_id="asset-1",
        author_id="user-1",
        type="box",
        geometry={"x": 0, "y": 0, "w": 10, "h": 10},
        class_name="dog",
    )

    result = bulk_save(
        db,
        author_id="user-1",
        creates=[],
        updates=[
            {
                "id": ann.id,
                "class_name": "cat",
                "expected_version": ann.version + 99,  # wrong
            }
        ],
        deletes=[],
    )
    statuses = [u["status"] for u in result["updated"]]
    assert statuses == ["conflict"]


def test_set_review_approves_and_clears(db):
    from app.services.annotation_service import (
        create_annotation,
        set_review,
        update_annotation,
    )

    _seed(db)
    ann = create_annotation(
        db,
        asset_id="asset-1",
        author_id="user-1",
        type="box",
        geometry={"x": 0, "y": 0, "w": 10, "h": 10},
        class_name="dog",
    )

    approved = set_review(
        db, ann.id, review_status="approved", reviewer_id="reviewer-1", notes="lgtm"
    )
    assert approved.review_status == "approved"
    assert approved.reviewer_id == "reviewer-1"
    assert approved.review_notes == "lgtm"

    # Updating an approved annotation invalidates the prior review.
    after = update_annotation(
        db, ann.id, geometry={"x": 2, "y": 2, "w": 12, "h": 12}, expected_version=ann.version
    )
    assert after.review_status == "unreviewed"
    assert after.reviewer_id is None


def test_review_summary_counts(db):
    from app.services.annotation_service import (
        create_annotation,
        review_summary,
        set_review,
    )

    _seed(db)
    a = create_annotation(
        db,
        asset_id="asset-1",
        author_id="user-1",
        type="box",
        geometry={"x": 0, "y": 0, "w": 10, "h": 10},
        class_name="dog",
    )
    b = create_annotation(
        db,
        asset_id="asset-1",
        author_id="user-1",
        type="box",
        geometry={"x": 1, "y": 1, "w": 11, "h": 11},
        class_name="cat",
    )
    c = create_annotation(
        db,
        asset_id="asset-1",
        author_id="user-1",
        type="box",
        geometry={"x": 2, "y": 2, "w": 12, "h": 12},
        class_name="cat",
    )
    set_review(db, a.id, review_status="approved", reviewer_id="reviewer-1")
    set_review(db, b.id, review_status="rejected", reviewer_id="reviewer-1")
    summary = review_summary(db, dataset_id="ds-1")
    assert summary["approved"] == 1
    assert summary["rejected"] == 1
    assert summary["unreviewed"] == 1
    assert summary["total"] == 3
    assert summary["flagged"] == 0
    assert c is not None  # silence unused warning
