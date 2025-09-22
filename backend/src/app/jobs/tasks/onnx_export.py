from __future__ import annotations

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover - fallback when Celery not installed
    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap


@shared_task(name="app.jobs.tasks.onnx_export.export_task")
def export_task(payload: dict) -> dict:
    try:
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.jobs_service import update_job_status

        db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")
        engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            if job_id := payload.get("jobId"):
                update_job_status(db, job_id, status="running", progress=0.1)
        finally:
            db.close()
    except Exception:
        pass

    # TODO: Perform ONNX export and validation
    result = {"status": "succeeded"}

    try:
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.jobs_service import update_job_status

        db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")
        engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            if job_id := payload.get("jobId"):
                update_job_status(db, job_id, status="succeeded", progress=1.0)
        finally:
            db.close()
    except Exception:
        pass

    return result
