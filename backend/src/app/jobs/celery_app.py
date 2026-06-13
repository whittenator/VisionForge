from __future__ import annotations

import os

try:
    from celery import Celery  # type: ignore
except Exception:  # pragma: no cover
    Celery = None  # type: ignore


class _DummyAsyncResult:
    def __init__(self) -> None:
        import uuid

        self.id = str(uuid.uuid4())


class _DummyCelery:
    def send_task(self, *args, **kwargs):  # pragma: no cover - used only when Celery missing
        # Simulate a queued job id; services catch exceptions if they require real enqueue
        raise RuntimeError("Celery is not available in this environment")


redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
if Celery is not None:
    celery_app = Celery(
        "visionforge",
        broker=redis_url,
        backend=redis_url,
        include=[
            "app.jobs.tasks.training",
            "app.jobs.tasks.evaluation",
            "app.jobs.tasks.onnx_export",
            "app.jobs.tasks.frame_extraction",
            "app.jobs.tasks.embeddings",
            "app.jobs.tasks.prelabels",
            "app.jobs.tasks.uncertainty",
            "app.jobs.tasks.error_mining",
            "app.jobs.tasks.al_uncertainty",
            "app.jobs.tasks.maintenance",
        ],
    )
    celery_app.conf.task_routes = {
        "app.jobs.tasks.*": {"queue": "default"},
    }
    # Hard ceiling for any task; training defaults to 24h, everything inherits
    # unless overridden per-task. acks_late + reject_on_worker_lost means a
    # task whose worker dies is redelivered instead of silently vanishing
    # (the visibility_timeout must exceed the longest task for Redis brokers).
    _task_time_limit = int(os.getenv("CELERY_TASK_TIME_LIMIT", str(24 * 3600)))
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_time_limit=_task_time_limit,
        task_soft_time_limit=max(_task_time_limit - 300, 60),
        broker_transport_options={"visibility_timeout": _task_time_limit + 3600},
        worker_prefetch_multiplier=int(os.getenv("CELERY_PREFETCH", "1")),
        broker_connection_retry_on_startup=True,
        beat_schedule={
            "sweep-stale-jobs": {
                "task": "app.jobs.tasks.maintenance.sweep_stale_jobs",
                "schedule": float(os.getenv("VF_JOB_SWEEP_INTERVAL", "300")),
            },
        },
    )
else:
    celery_app = _DummyCelery()  # type: ignore
