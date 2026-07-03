"""Request-level tests for the dataset-wide prelabel endpoint (``api/ops.py``).

Covers the two contract-critical branches:

* ``409`` when the dataset has no trained model to prelabel with.
* ``202 queued`` when a successful model artifact exists — dispatch is mocked
  by the autouse ``_hermetic_celery`` fixture in ``conftest.py``.
"""

from __future__ import annotations

import uuid

from app.db.deps import get_current_user
from app.main import app
from app.models.artifact import ModelArtifact
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.experiment import ExperimentRun
from app.models.user import User
from tests.conftest import TestingSessionLocal, client, ensure_project


def _fake_user() -> User:
    return User(id="prelabel-tester", email="prelabel@example.com", name="T", password_hash="x")


app.dependency_overrides[get_current_user] = _fake_user


def _seed_dataset_with_version(*, task_type: str | None = "detect") -> tuple[str, str]:
    """Create a dataset (in project ``p``) with a single version. Returns ids."""
    ensure_project("p")
    db = TestingSessionLocal()
    try:
        ds = Dataset(id=str(uuid.uuid4()), project_id="p", name="ds", task_type=task_type)
        db.add(ds)
        db.commit()
        version = DatasetVersion(id=str(uuid.uuid4()), dataset_id=ds.id, version=1)
        db.add(version)
        db.commit()
        return ds.id, version.id
    finally:
        db.close()


def _seed_model_artifact(dataset_id: str, version_id: str, storage_path: str) -> str:
    """Attach a successful run + artifact to a dataset version so it is a
    candidate for ``latest_artifact_for_dataset``."""
    db = TestingSessionLocal()
    try:
        run = ExperimentRun(
            id=str(uuid.uuid4()),
            project_id="p",
            dataset_version_id=version_id,
            owner_id="prelabel-tester",
            status="succeeded",
        )
        db.add(run)
        db.commit()
        art = ModelArtifact(
            id=str(uuid.uuid4()),
            project_id="p",
            run_id=run.id,
            type="pytorch",
            storage_path=storage_path,
        )
        db.add(art)
        db.commit()
        return art.id
    finally:
        db.close()


def test_prelabel_returns_409_when_no_model():
    ds_id, _ = _seed_dataset_with_version()
    r = client.post(f"/api/datasets/{ds_id}/prelabel")
    assert r.status_code == 409, r.text
    assert "no trained model" in r.json()["detail"]


def test_prelabel_queues_job_when_model_exists():
    from app.jobs.celery_app import celery_app

    ds_id, version_id = _seed_dataset_with_version()
    _seed_model_artifact(ds_id, version_id, "models/best.pt")

    r = client.post(f"/api/datasets/{ds_id}/prelabel?conf_threshold=0.4")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["jobId"]

    # The hermetic fixture patches send_task to a MagicMock; assert the task
    # name and the payload we handed it.
    celery_app.send_task.assert_called_once()
    call = celery_app.send_task.call_args
    assert call.args[0] == "app.jobs.tasks.prelabels.apply_prelabels"
    payload = call.kwargs["args"][0]
    assert payload["jobId"] == body["jobId"]
    assert payload["datasetVersionId"] == version_id
    assert payload["modelKey"] == "models/best.pt"
    assert payload["task"] == "detect"
    assert payload["confThreshold"] == 0.4


def test_prelabel_404_for_unknown_dataset():
    r = client.post(f"/api/datasets/{uuid.uuid4()}/prelabel")
    assert r.status_code == 404
