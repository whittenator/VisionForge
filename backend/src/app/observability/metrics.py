from __future__ import annotations

import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "vf_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "vf_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
active_requests = Gauge(
    "vf_http_active_requests",
    "Number of currently active HTTP requests",
)
training_jobs_total = Counter(
    "vf_training_jobs_total",
    "Total training jobs by status",
    ["status"],
)
annotation_saves_total = Counter(
    "vf_annotation_saves_total",
    "Total annotation save operations",
    ["type"],
)
asset_uploads_total = Counter(
    "vf_asset_uploads_total",
    "Total asset upload confirmations",
)


def metrics_middleware(app):
    async def _middleware(request, call_next: Callable):
        start = time.perf_counter()
        active_requests.inc()
        try:
            response = await call_next(request)
        finally:
            active_requests.dec()
        duration = time.perf_counter() - start
        # Use route path template to avoid cardinality explosion from UUIDs
        path = getattr(request.scope.get("route"), "path", request.url.path)
        status = str(response.status_code)
        http_requests_total.labels(request.method, path, status).inc()
        http_request_duration_seconds.labels(request.method, path).observe(duration)
        return response

    return _middleware
