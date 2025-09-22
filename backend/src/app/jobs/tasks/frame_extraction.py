try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap


@shared_task(name="app.jobs.tasks.frame_extraction.extract_frames")
def extract_frames(payload: dict) -> dict:
    # Update job running -> succeeded
    _touch_status(payload, "running", 0.2)
    _touch_status(payload, "succeeded", 1.0)
    return {"status": "succeeded", "frames": []}


def _touch_status(payload: dict, status: str, progress: float) -> None:
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
                update_job_status(db, job_id, status=status, progress=progress)
        finally:
            db.close()
    except Exception:
        pass
