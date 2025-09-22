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
    )
    celery_app.conf.task_routes = {
        "app.jobs.tasks.*": {"queue": "default"},
    }
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        worker_prefetch_multiplier=int(os.getenv("CELERY_PREFETCH", "4")),
        broker_connection_retry_on_startup=True,
    )
else:
    celery_app = _DummyCelery()  # type: ignore
