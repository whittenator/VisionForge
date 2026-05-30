"""Unit tests for suggestion_service. Inference + storage are monkeypatched so
the suite stays hermetic (no real models, no MinIO)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


def _register_models() -> None:
    """Import the ORM models so their tables register on Base.metadata before
    create_all (the app conftest does this transitively; we do it explicitly so
    the suite also runs standalone)."""
    import app.models.annotation  # noqa: F401
    import app.models.artifact  # noqa: F401
    import app.models.asset  # noqa: F401
    import app.models.dataset  # noqa: F401
    import app.models.dataset_version  # noqa: F401
    import app.models.experiment  # noqa: F401
    import app.models.project  # noqa: F401
    import app.models.user  # noqa: F401
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


def _seed(db):
    """Dataset + two versions + asset; returns ids."""
    from app.models.asset import Asset
    from app.models.dataset import Dataset
    from app.models.dataset_version import DatasetVersion
    from app.models.project import Project
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="WS", created_by="user-1"))
    db.add(Project(id="proj-1", workspace_id="ws-1", name="P", slug="p"))
    db.add(Dataset(id="ds-1", project_id="proj-1", name="DS"))
    db.add(DatasetVersion(id="ver-1", dataset_id="ds-1", version=1))
    db.add(
        Asset(
            id="asset-1",
            dataset_id="ds-1",
            version_id="ver-1",
            uri="datasets/v1/a.jpg",
            mime_type="image/jpeg",
            label_status="unlabeled",
        )
    )
    db.commit()


def _add_run_and_artifact(db, *, run_id, artifact_id, status, created_offset_days, name="m"):
    from app.models.artifact import ModelArtifact
    from app.models.experiment import ExperimentRun

    db.add(
        ExperimentRun(
            id=run_id,
            project_id="proj-1",
            dataset_version_id="ver-1",
            owner_id="user-1",
            status=status,
        )
    )
    db.add(
        ModelArtifact(
            id=artifact_id,
            project_id="proj-1",
            run_id=run_id,
            name=name,
            version="1",
            type="yolo",
            format="pt",
            storage_path=f"models/{artifact_id}.pt",
            created_at=datetime.now(timezone.utc) + timedelta(days=created_offset_days),
        )
    )
    db.commit()


def test_latest_artifact_picks_newest_succeeded(db):
    from app.services import suggestion_service

    _seed(db)
    _add_run_and_artifact(
        db, run_id="r1", artifact_id="art-old", status="succeeded", created_offset_days=-2
    )
    _add_run_and_artifact(
        db, run_id="r2", artifact_id="art-new", status="succeeded", created_offset_days=-1
    )
    # A failed run's artifact must be ignored.
    _add_run_and_artifact(
        db, run_id="r3", artifact_id="art-fail", status="failed", created_offset_days=0
    )

    latest = suggestion_service.latest_artifact_for_dataset(db, "ds-1")
    assert latest is not None
    assert latest.id == "art-new"

    candidates = suggestion_service.candidate_artifacts_for_dataset(db, "ds-1")
    assert [a.id for a in candidates] == ["art-new", "art-old"]


def test_no_model_raises(db):
    from app.services import suggestion_service

    _seed(db)
    with pytest.raises(suggestion_service.NoModelError):
        suggestion_service.suggest_annotations(db, asset_id="asset-1")


def test_suggest_maps_detections(db, monkeypatch):
    from app.services import inference_service, suggestion_service

    _seed(db)
    _add_run_and_artifact(
        db, run_id="r1", artifact_id="art-1", status="succeeded", created_offset_days=-1
    )

    monkeypatch.setattr(suggestion_service, "_load_image_bytes", lambda asset: b"img")
    monkeypatch.setattr(
        inference_service,
        "predict",
        lambda artifact, image_bytes, **kw: {
            "detections": [
                {"class": "cat", "bbox": [10, 20, 30, 40], "score": 0.9},
                {"class": "dog", "bbox": [1, 2, 3, 4], "score": 0.5},
            ],
            "classification": {"class": "animal", "score": 0.8},
        },
    )

    artifact, suggestions = suggestion_service.suggest_annotations(db, asset_id="asset-1")
    assert artifact.id == "art-1"
    boxes = [s for s in suggestions if s.type == "box"]
    assert len(boxes) == 2
    assert boxes[0].geometry == {"x": 10, "y": 20, "w": 30, "h": 40}
    assert boxes[0].class_name == "cat"
    assert boxes[0].score == 0.9
    cls = [s for s in suggestions if s.type == "classification"]
    assert len(cls) == 1
    assert cls[0].class_name == "animal"


def test_override_must_belong_to_dataset(db, monkeypatch):
    from app.models.artifact import ModelArtifact
    from app.models.experiment import ExperimentRun
    from app.services import suggestion_service

    _seed(db)
    _add_run_and_artifact(
        db, run_id="r1", artifact_id="art-1", status="succeeded", created_offset_days=-1
    )
    # An artifact from an unrelated run/dataset version.
    db.add(
        ExperimentRun(
            id="r-other",
            project_id="proj-1",
            dataset_version_id="ver-other",
            owner_id="user-1",
            status="succeeded",
        )
    )
    db.add(
        ModelArtifact(
            id="art-other",
            project_id="proj-1",
            run_id="r-other",
            name="other",
            version="1",
            type="yolo",
            format="pt",
            storage_path="models/other.pt",
        )
    )
    db.commit()

    monkeypatch.setattr(suggestion_service, "_load_image_bytes", lambda asset: b"img")
    with pytest.raises(suggestion_service.SuggestionError):
        suggestion_service.suggest_annotations(db, asset_id="asset-1", artifact_id="art-other")
