"""Phase 2 task_type behaviour on Project + Dataset."""

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


def _ws(db):
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="W", created_by="user-1"))
    db.commit()


def test_create_project_persists_task_type(db):
    from app.services.project_dataset_service import create_project

    _ws(db)
    p = create_project(db, "Detector", "obj det", task_type="detect", workspace_id="ws-1")
    assert p.task_type == "detect"


def test_create_project_rejects_unknown_task_type(db):
    from app.services.project_dataset_service import create_project

    _ws(db)
    with pytest.raises(ValueError):
        create_project(db, "X", None, task_type="bogus", workspace_id="ws-1")


def test_dataset_inherits_project_task_type(db):
    from app.services.project_dataset_service import create_dataset, create_project

    _ws(db)
    p = create_project(db, "Classifier", None, task_type="classify", workspace_id="ws-1")
    dataset, version = create_dataset(db, p.id, "default", None)
    assert dataset.task_type == "classify"
    assert version.version == 1


def test_training_rejects_task_type_mismatch(db):
    from app.models.dataset_version import DatasetVersion
    from app.services.project_dataset_service import create_dataset, create_project
    from app.services.training_service import TaskTypeMismatch, launch_training

    _ws(db)
    p = create_project(db, "Detector", None, task_type="detect", workspace_id="ws-1")
    dataset, _ = create_dataset(db, p.id, "default", None)
    # Force the dataset's first version into the test scope.
    version = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset.id).first()
    assert version is not None

    with pytest.raises(TaskTypeMismatch):
        launch_training(
            db,
            p.id,
            version.id,
            task="classify",
            params={},
            owner_id="user-1",
        )
