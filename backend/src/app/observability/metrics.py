from __future__ import annotations

import time
from typing import Callable

from prometheus_client import Counter, Histogram

http_requests_total = Counter(
    "vf_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "vf_http_request_duration_seconds",
    "HTTP request latency in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


def metrics_middleware(app):
    async def _middleware(request, call_next: Callable):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = getattr(request.scope.get("route"), "path", request.url.path)
        http_requests_total.labels(request.method, path, str(response.status_code)).inc()
        http_request_duration_seconds.observe(duration)
        return response

    return _middleware
