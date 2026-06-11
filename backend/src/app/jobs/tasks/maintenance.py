from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import structlog

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover

    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn

        return _wrap


logger = structlog.get_logger(__name__)

# A job is considered stuck when it has reported no progress for this long.
# Training commits progress at least once per epoch, so 6h is conservative.
_STALE_RUNNING_SECONDS = int(os.getenv("VF_JOB_STALE_RUNNING_SECONDS", str(6 * 3600)))
# A job that never left "queued" (e.g. enqueued while the broker was down,
# or its dedicated cluster never picked it up) is failed after this long.
_STALE_QUEUED_SECONDS = int(os.getenv("VF_JOB_STALE_QUEUED_SECONDS", str(24 * 3600)))


def _make_session():
    from app.db.session import SessionLocal

    return SessionLocal()


@shared_task(name="app.jobs.tasks.maintenance.sweep_stale_jobs")
def sweep_stale_jobs() -> dict:
    """Fail stuck jobs and release their clusters (runs via celery beat).

    Safety net for the cases task-level error handling can't cover: a worker
    killed mid-task, a broker outage after the job row was created, or an
    agent that vanished while holding a cluster reservation.
    """
    from app.models.cluster import Cluster
    from app.models.job import Job
    from app.services.jobs_service import update_job_status

    db = _make_session()
    swept: list[str] = []
    released: list[str] = []
    try:
        now = datetime.now(timezone.utc)
        candidates = db.query(Job).filter(Job.status.in_(["queued", "running"])).all()  # noqa: E501
        for job in candidates:
            ref = job.updated_at or job.created_at
            if ref is None:
                continue
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            limit = _STALE_RUNNING_SECONDS if job.status == "running" else _STALE_QUEUED_SECONDS
            if now - ref > timedelta(seconds=limit):
                job.error_message = (
                    f"Swept by maintenance: no progress for over {limit}s " f"while {job.status}"
                )
                db.add(job)
                db.commit()
                # update_job_status also releases any cluster reserved for the job.
                update_job_status(db, job.id, status="failed")
                swept.append(job.id)

        # Release clusters whose reserved job is already terminal or gone.
        busy = db.query(Cluster).filter(Cluster.active_job_id.isnot(None)).all()
        for cluster in busy:
            job = db.get(Job, cluster.active_job_id)
            if job is None or job.status in ("succeeded", "failed", "cancelled"):
                cluster.active_job_id = None
                if cluster.status == "busy":
                    cluster.status = "online"
                db.add(cluster)
                db.commit()
                released.append(cluster.id)
    finally:
        db.close()

    if swept or released:
        logger.warning("maintenance:swept", jobs=swept, clusters=released)
    return {"swept_jobs": swept, "released_clusters": released}
