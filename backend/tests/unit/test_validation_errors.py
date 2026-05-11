"""Unit tests for validation rules and error paths in service-layer code."""

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


def _seed_asset(db, asset_id: str = "asset-1", dataset_id: str = "ds-1") -> str:
    from app.models.asset import Asset
    from app.models.dataset import Dataset
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="WS", created_by="u1"))
    db.add(Project(id="p-1", workspace_id="ws-1", name="P", slug="p-1"))
    db.add(Dataset(id=dataset_id, project_id="p-1", name="D"))
    db.add(User(id="u1", name="U", email="u1@example.com"))
    db.add(
        Asset(
            id=asset_id,
            dataset_id=dataset_id,
            uri=f"datasets/{dataset_id}/img.jpg",
            mime_type="image/jpeg",
            label_status="unlabeled",
        )
    )
    db.commit()
    return asset_id


# --- annotation_service validation -------------------------------------------------


def test_create_annotation_rejects_unknown_type(db):
    from app.services.annotation_service import AnnotationError, create_annotation

    _seed_asset(db)
    with pytest.raises(AnnotationError, match="unsupported annotation type"):
        create_annotation(
            db,
            asset_id="asset-1",
            author_id="u1",
            type="ellipse",
            geometry={"x": 0, "y": 0, "w": 1, "h": 1},
            class_name="x",
        )


def test_box_geometry_requires_all_coordinates(db):
    from app.services.annotation_service import AnnotationError, create_annotation

    _seed_asset(db)
    with pytest.raises(AnnotationError, match="missing 'h'"):
        create_annotation(
            db,
            asset_id="asset-1",
            author_id="u1",
            type="box",
            geometry={"x": 0, "y": 0, "w": 5},
            class_name="x",
        )


def test_box_geometry_rejects_zero_size(db):
    from app.services.annotation_service import AnnotationError, create_annotation

    _seed_asset(db)
    with pytest.raises(AnnotationError, match="positive width/height"):
        create_annotation(
            db,
            asset_id="asset-1",
            author_id="u1",
            type="box",
            geometry={"x": 0, "y": 0, "w": 0, "h": 10},
            class_name="x",
        )


def test_polygon_requires_three_points(db):
    from app.services.annotation_service import AnnotationError, create_annotation

    _seed_asset(db)
    with pytest.raises(AnnotationError, match="at least 3 points"):
        create_annotation(
            db,
            asset_id="asset-1",
            author_id="u1",
            type="polygon",
            geometry={"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]},
            class_name="x",
        )


def test_polygon_point_must_have_x_and_y(db):
    from app.services.annotation_service import AnnotationError, create_annotation

    _seed_asset(db)
    with pytest.raises(AnnotationError, match="missing 'x' or 'y'"):
        create_annotation(
            db,
            asset_id="asset-1",
            author_id="u1",
            type="polygon",
            geometry={"points": [{"x": 0, "y": 0}, {"x": 1}, {"x": 2, "y": 2}]},
            class_name="x",
        )


def test_keypoint_requires_at_least_one_point(db):
    from app.services.annotation_service import AnnotationError, create_annotation

    _seed_asset(db)
    with pytest.raises(AnnotationError, match="at least 1 point"):
        create_annotation(
            db,
            asset_id="asset-1",
            author_id="u1",
            type="keypoint",
            geometry={"points": []},
            class_name="x",
        )


def test_update_annotation_returns_none_for_missing_id(db):
    from app.services.annotation_service import update_annotation

    _seed_asset(db)
    result = update_annotation(db, "does-not-exist", class_name="x")
    assert result is None


def test_update_annotation_raises_on_version_mismatch(db):
    from app.services.annotation_service import (
        VersionConflictError,
        create_annotation,
        update_annotation,
    )

    _seed_asset(db)
    ann = create_annotation(
        db,
        asset_id="asset-1",
        author_id="u1",
        type="box",
        geometry={"x": 0, "y": 0, "w": 5, "h": 5},
        class_name="cat",
    )
    with pytest.raises(VersionConflictError):
        update_annotation(
            db, ann.id, geometry={"x": 1, "y": 1, "w": 5, "h": 5}, expected_version=99
        )


def test_update_annotation_no_op_does_not_bump_version(db):
    """A no-field update should NOT increment version (avoids spurious lock conflicts)."""
    from app.services.annotation_service import create_annotation, update_annotation

    _seed_asset(db)
    ann = create_annotation(
        db,
        asset_id="asset-1",
        author_id="u1",
        type="box",
        geometry={"x": 0, "y": 0, "w": 5, "h": 5},
        class_name="cat",
    )
    initial_version = ann.version
    same = update_annotation(db, ann.id, class_name="cat")
    assert same is not None
    assert same.version == initial_version


def test_delete_annotation_returns_false_for_missing_id(db):
    from app.services.annotation_service import delete_annotation

    _seed_asset(db)
    assert delete_annotation(db, "does-not-exist") is False


def test_get_history_returns_empty_for_missing_annotation(db):
    from app.services.annotation_service import get_history

    _seed_asset(db)
    assert get_history(db, "does-not-exist") == []


# --- cluster_service error paths ---------------------------------------------------


def test_reserve_unknown_cluster_raises(db):
    from app.services import cluster_service

    with pytest.raises(cluster_service.ClusterNotAvailableError, match="not found"):
        cluster_service.reserve_cluster(db, "missing-id", "j1", kind="train")


# --- pydantic schema validation ---------------------------------------------------


def test_upload_url_request_requires_dataset_version_id():
    from pydantic import ValidationError

    from app.schemas.common import UploadUrlRequest

    with pytest.raises(ValidationError):
        UploadUrlRequest(filename="x.bin")  # type: ignore[call-arg]


def test_upload_url_request_accepts_minimal_payload():
    from app.schemas.common import UploadUrlRequest

    req = UploadUrlRequest(datasetVersionId="v1", filename="x.bin")
    assert req.contentType is None
