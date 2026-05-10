"""When the broker is down, export_onnx must mark the job failed (not queued)."""

from __future__ import annotations

from unittest import mock

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


def _seed_project_and_run(db) -> str:
    """Create a minimal Project + ExperimentRun and return the run id."""
    from app.models.experiment import ExperimentRun
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    db.add(Workspace(id="ws-1", name="W", created_by="user-1"))
    db.add(Project(id="p-1", workspace_id="ws-1", name="P", slug="p"))
    db.add(User(id="user-1", name="U", email="u@u.com"))
    run = ExperimentRun(
        id="run-1",
        project_id="p-1",
        owner_id="user-1",
        name="r",
        status="succeeded",
    )
    db.add(run)
    db.commit()
    return run.id


def test_dispatch_failure_marks_job_failed(db):
    """If celery_app.send_task explodes, the job row must end up `failed`."""
    from app.models.job import Job
    from app.services.onnx_service import OnnxDispatchError, export_onnx

    run_id = _seed_project_and_run(db)

    with mock.patch(
        "app.services.onnx_service.celery_app.send_task",
        side_effect=RuntimeError("broker unreachable"),
    ):
        with pytest.raises(OnnxDispatchError):
            export_onnx(db, run_id, dynamic_axes=True)

    # Find the most recently created job and assert it's failed.
    jobs = db.query(Job).filter(Job.type == "onnx_export").all()
    assert jobs, "expected an onnx_export job row to be created"
    assert jobs[-1].status == "failed"
