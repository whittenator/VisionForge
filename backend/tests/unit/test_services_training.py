from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.training_service import launch_training


def test_launch_training_returns_job_id(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    try:
        result = launch_training(db, project_id="p1", dataset_version_id="dv1", task="detect")
        assert result["status"] == "queued"
        assert result["type"] == "train"
        assert result["jobId"]
    finally:
        db.close()
