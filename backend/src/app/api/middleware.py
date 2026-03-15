from __future__ import annotations

import time
import traceback
import uuid
from typing import Callable

import structlog
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


def logging_middleware():
    async def _mw(request, call_next: Callable):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        log = logger.bind(request_id=request_id, method=request.method, path=request.url.path)
        log.info("request:start")
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised via integration
            log.error("request:error", error=str(exc), tb=traceback.format_exc())
            return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        log.info("request:end", status=response.status_code, duration_ms=duration_ms)
        response.headers["X-Request-ID"] = request_id
        return response

    return _mw


# Rate limiting for auth endpoints (simple in-memory, replace with Redis in prod)
_auth_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 10  # per window
_WINDOW_SECONDS = 60


def auth_rate_limit_middleware():
    """Simple in-memory rate limiter for /auth/* endpoints."""
    async def _mw(request, call_next: Callable):
        if request.url.path.startswith("/auth/"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window_start = now - _WINDOW_SECONDS
            attempts = _auth_attempts.get(client_ip, [])
            # Prune old entries
            attempts = [t for t in attempts if t > window_start]
            if len(attempts) >= _MAX_ATTEMPTS:
                return JSONResponse(
                    {"detail": "Too many requests. Please wait before trying again."},
                    status_code=429,
                    headers={"Retry-After": str(_WINDOW_SECONDS)},
                )
            attempts.append(now)
            _auth_attempts[client_ip] = attempts
        return await call_next(request)

    return _mw
