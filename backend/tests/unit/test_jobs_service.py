import json
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_create_and_update_job(tmp_path):
    # Ensure backend/src is on sys.path relative to this file
    current_dir = os.path.dirname(__file__)
    src_path = os.path.abspath(os.path.join(current_dir, "..", "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from app import models as _models  # noqa: F401
    from app.db.base import Base
    from app.services.jobs_service import create_job, update_job_status

    # SQLite DB for unit test
    db_path = tmp_path / "jobs.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    try:
        payload = {"k": "v"}
        job = create_job(db, "train", payload)
        assert job.id
        assert job.type == "train"
        assert json.loads(job.payload_json) == payload
        assert job.status == "queued"
        assert job.progress == 0.0

        job2 = update_job_status(db, job.id, status="running", progress=0.5)
        assert job2.status == "running"
        assert job2.progress == 0.5

        job3 = update_job_status(db, job.id, status="succeeded", progress=1.0, logs_uri="s3://bucket/logs.txt")
        assert job3.status == "succeeded"
        assert job3.progress == 1.0
        assert job3.logs_uri is not None
    finally:
        db.close()
