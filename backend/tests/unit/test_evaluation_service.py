"""Unit tests for ``services/evaluation_service``.

Covers the previously-untested pure helpers (``summarize`` / ``to_dict`` /
``write_result``), the paginated ``list_evaluations`` query, and the
``create_evaluation`` flow — including its validation errors. Celery dispatch is
stubbed so no broker is required.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.artifact import ModelArtifact
from app.models.dataset_version import DatasetVersion
from app.models.evaluation import Evaluation
from app.schemas.evaluation import EvaluationCreate
from app.services import evaluation_service
from tests.conftest import TestingSessionLocal


def _mk_eval(db, **kwargs) -> Evaluation:
    row = Evaluation(
        id=str(uuid.uuid4()),
        project_id=kwargs.pop("project_id", "proj"),
        artifact_id=kwargs.pop("artifact_id", "art"),
        dataset_version_id=kwargs.pop("dataset_version_id", "ver"),
        status=kwargs.pop("status", "queued"),
        **kwargs,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_summarize_picks_first_available_primary_metric():
    row = Evaluation(
        id="e1",
        project_id="p",
        artifact_id="a",
        dataset_version_id="v",
        status="succeeded",
        metrics_json='{"precision": 0.7, "mAP50": 0.81}',
    )
    out = evaluation_service.summarize(row)
    # mAP50 wins over precision because it comes first in the priority list.
    assert out["primary_metric_name"] == "mAP50"
    assert out["primary_metric"] == 0.81


def test_summarize_handles_missing_and_bad_metrics():
    row = Evaluation(
        id="e2",
        project_id="p",
        artifact_id="a",
        dataset_version_id="v",
        status="failed",
        metrics_json="not-json",
    )
    out = evaluation_service.summarize(row)
    assert out["primary_metric"] is None
    assert out["primary_metric_name"] is None


def test_to_dict_parses_json_columns():
    row = Evaluation(
        id="e3",
        project_id="p",
        artifact_id="a",
        dataset_version_id="v",
        status="succeeded",
        metrics_json='{"mAP50": 0.5}',
        confusion_json="[[1,2],[3,4]]",
        classes_json='["cat","dog"]',
    )
    out = evaluation_service.to_dict(row)
    assert out["metrics"] == {"mAP50": 0.5}
    assert out["confusion"] == [[1, 2], [3, 4]]
    assert out["classes"] == ["cat", "dog"]
    # Unset JSON columns fall back to None rather than raising.
    assert out["per_class"] is None


def test_write_result_persists_status_and_completion():
    db = TestingSessionLocal()
    try:
        row = _mk_eval(db, status="running")
        updated = evaluation_service.write_result(
            db, row.id, status="succeeded", metrics={"mAP50": 0.9}
        )
        assert updated.status == "succeeded"
        assert updated.completed_at is not None
        assert evaluation_service.to_dict(updated)["metrics"] == {"mAP50": 0.9}
    finally:
        db.close()


def test_write_result_returns_none_for_unknown_id():
    db = TestingSessionLocal()
    try:
        assert evaluation_service.write_result(db, "missing", status="failed") is None
    finally:
        db.close()


def test_list_evaluations_filters_and_paginates():
    db = TestingSessionLocal()
    try:
        art = uuid.uuid4().hex
        for _ in range(3):
            _mk_eval(db, artifact_id=art)
        _mk_eval(db, artifact_id="other")

        rows, total = evaluation_service.list_evaluations(
            db, artifact_id=art, page=1, page_size=2, return_total=True
        )
        assert total == 3
        assert len(rows) == 2

        flat = evaluation_service.list_evaluations(db, artifact_id=art)
        assert len(flat) == 3
    finally:
        db.close()


def test_create_evaluation_validates_artifact_and_version(monkeypatch):
    db = TestingSessionLocal()
    try:
        payload = EvaluationCreate(artifact_id="nope", dataset_version_id="nope")
        with pytest.raises(evaluation_service.EvaluationError):
            evaluation_service.create_evaluation(db, payload)
    finally:
        db.close()


def test_create_evaluation_dispatches_without_cluster(monkeypatch):
    # Stub Celery so the broker is never contacted.
    sent: list = []
    monkeypatch.setattr(
        evaluation_service.celery_app,
        "send_task",
        lambda name, **kw: sent.append((name, kw)),
    )

    db = TestingSessionLocal()
    try:
        ver = DatasetVersion(id=str(uuid.uuid4()), dataset_id="ds", version=1)
        art = ModelArtifact(
            id=str(uuid.uuid4()), project_id="proj", type="pytorch", format="pytorch"
        )
        db.add_all([ver, art])
        db.commit()

        payload = EvaluationCreate(artifact_id=art.id, dataset_version_id=ver.id)
        eval_row, job = evaluation_service.create_evaluation(db, payload)

        assert eval_row.status == "queued"
        assert job["evaluationId"] == eval_row.id
        assert job["jobId"]
        assert sent and sent[0][0] == "app.jobs.tasks.evaluation.evaluate_task"
    finally:
        db.close()
