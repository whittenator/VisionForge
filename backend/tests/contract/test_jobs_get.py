import os
import sys

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_get_job_returns_status():
    # Ensure backend/src is importable (contract tests folder -> ../src)
    current_dir = os.path.dirname(__file__)
    src_path = os.path.abspath(os.path.join(current_dir, "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from app.db.deps import get_db
    from app.main import app
    from app.services.jobs_service import create_job

    client = TestClient(app)

    # Create a job in the DB
    db: Session = next(app.dependency_overrides[get_db]()) if get_db in app.dependency_overrides else None
    if db is None:
        # Fallback to building a Session like conftest does is unnecessary here; tests set override
        raise RuntimeError("DB override not set for tests")

    try:
        job = create_job(db, "train", {"hello": "world"})
    finally:
        db.close()

    # Fetch via API
    resp = client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job.id
    assert data["jobId"] == job.id
    assert data["type"] == "train"
    assert data["status"] == "queued"
    assert data["progress"] == 0.0
