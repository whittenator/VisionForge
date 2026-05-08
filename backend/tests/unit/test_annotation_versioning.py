import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as _models  # noqa: F401
from app.db.base import Base
from app.models.asset import Asset
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.user import User
from app.services.annotation_service import (
    AnnotationError,
    VersionConflictError,
    create_annotation,
    delete_annotation,
    get_history,
    update_annotation,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    user = User(id="u1", email="u@example.com", name="U", password_hash="$2b$x")
    s.add(user)
    ds = Dataset(id="ds1", project_id="p1", name="d", description="")
    s.add(ds)
    s.commit()
    v = DatasetVersion(id="dv1", dataset_id="ds1", version=1)
    s.add(v)
    s.commit()
    asset = Asset(
        id="a1",
        dataset_id="ds1",
        version_id="dv1",
        uri="x",
        mime_type="image/jpeg",
        label_status="unlabelled",
    )
    s.add(asset)
    s.commit()
    try:
        yield s
    finally:
        s.close()


def test_create_box(db):
    a = create_annotation(
        db,
        asset_id="a1",
        author_id="u1",
        type="box",
        geometry={"x": 1, "y": 2, "w": 3, "h": 4},
        class_name="car",
    )
    assert a.id and a.version == 1
    assert a.updated_at is not None


def test_create_polygon_requires_three_points(db):
    with pytest.raises(AnnotationError):
        create_annotation(
            db,
            asset_id="a1",
            author_id="u1",
            type="polygon",
            geometry={"points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]},
            class_name="x",
        )

    a = create_annotation(
        db,
        asset_id="a1",
        author_id="u1",
        type="polygon",
        geometry={"points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 0, "y": 1}]},
        class_name="x",
    )
    assert a.type == "polygon"


def test_create_keypoint(db):
    a = create_annotation(
        db,
        asset_id="a1",
        author_id="u1",
        type="keypoint",
        geometry={"points": [{"x": 5, "y": 5}]},
        class_name="nose",
    )
    assert a.type == "keypoint"


def test_unsupported_type_rejected(db):
    with pytest.raises(AnnotationError):
        create_annotation(
            db,
            asset_id="a1",
            author_id="u1",
            type="cuboid",
            geometry={},
            class_name=None,
        )


def test_update_bumps_version_and_writes_history(db):
    a = create_annotation(
        db,
        asset_id="a1",
        author_id="u1",
        type="box",
        geometry={"x": 1, "y": 1, "w": 2, "h": 2},
        class_name="car",
    )
    updated = update_annotation(
        db,
        a.id,
        geometry={"x": 5, "y": 5, "w": 2, "h": 2},
        expected_version=1,
    )
    assert updated.version == 2
    history = get_history(db, a.id)
    assert len(history) == 1


def test_update_with_wrong_version_raises_409(db):
    a = create_annotation(
        db,
        asset_id="a1",
        author_id="u1",
        type="box",
        geometry={"x": 1, "y": 1, "w": 2, "h": 2},
        class_name="car",
    )
    with pytest.raises(VersionConflictError):
        update_annotation(
            db,
            a.id,
            geometry={"x": 5, "y": 5, "w": 2, "h": 2},
            expected_version=99,
        )


def test_delete(db):
    a = create_annotation(
        db,
        asset_id="a1",
        author_id="u1",
        type="box",
        geometry={"x": 1, "y": 1, "w": 2, "h": 2},
        class_name="car",
    )
    assert delete_annotation(db, a.id) is True
    assert delete_annotation(db, a.id) is False
