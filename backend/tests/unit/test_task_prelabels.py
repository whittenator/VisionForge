"""Unit tests for the prelabeling Celery task.

With ``MINIO_DISABLED=true`` and no model key, the task can't load a model, so
it makes no predictions — but it must still walk the unlabeled assets, leave
them untouched, drive the Job to ``succeeded``, and report accurate counts.
We also cover the helper that extracts a storage key from an asset URI.
"""

from __future__ import annotations

import uuid

from app.jobs.tasks import prelabels as prelabels_task
from app.jobs.tasks.prelabels import _extract_minio_key
from app.models.asset import Asset
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.services.jobs_service import create_job
from tests.conftest import TestingSessionLocal


def _mk_version_with_assets(db, n: int) -> str:
    ds = Dataset(id=str(uuid.uuid4()), project_id="p", name="ds")
    db.add(ds)
    db.commit()
    ver = DatasetVersion(id=str(uuid.uuid4()), dataset_id=ds.id, version=1)
    db.add(ver)
    db.commit()
    for _ in range(n):
        db.add(
            Asset(
                id=str(uuid.uuid4()),
                dataset_id=ds.id,
                version_id=ver.id,
                uri=f"s3://bucket/{uuid.uuid4().hex}.jpg",
                mime_type="image/jpeg",
                label_status="unlabelled",
            )
        )
    db.commit()
    return ver.id


def test_extract_minio_key_handles_uri_schemes():
    assert _extract_minio_key("s3://bucket/path/to/img.jpg") == "path/to/img.jpg"
    assert _extract_minio_key("minio://bucket/img.jpg") == "img.jpg"
    # For http(s) the scheme + host are stripped, leaving bucket/key.
    assert _extract_minio_key("https://host/bucket/img.jpg") == "bucket/img.jpg"
    # A bare key (no scheme) is returned unchanged.
    assert _extract_minio_key("plain/key.jpg") == "plain/key.jpg"


def test_apply_prelabels_no_model_is_noop_but_succeeds():
    db = TestingSessionLocal()
    version_id = _mk_version_with_assets(db, 3)
    job = create_job(db, "prelabels", {"datasetVersionId": version_id})
    job_id = job.id
    db.close()

    result = prelabels_task.apply_prelabels(
        {"jobId": job_id, "datasetVersionId": version_id, "task": "detect"}
    )

    assert result["status"] == "succeeded"
    assert result["total_assets"] == 3
    assert result["labeled_count"] == 0

    check = TestingSessionLocal()
    try:
        from app.models.job import Job

        assert check.get(Job, job_id).status == "succeeded"
        # No annotations were invented, so assets stay unlabelled.
        remaining = (
            check.query(Asset)
            .filter(Asset.version_id == version_id, Asset.label_status == "unlabelled")
            .count()
        )
        assert remaining == 3
    finally:
        check.close()


def test_apply_prelabels_no_version_succeeds_with_zero_assets():
    db = TestingSessionLocal()
    job = create_job(db, "prelabels", {})
    job_id = job.id
    db.close()

    result = prelabels_task.apply_prelabels({"jobId": job_id})

    assert result["status"] == "succeeded"
    assert result["total_assets"] == 0
