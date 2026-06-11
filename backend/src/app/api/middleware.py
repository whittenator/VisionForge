from __future__ import annotations

import os
import time
import traceback
import uuid
from collections.abc import Callable

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


# Rate limiting for auth endpoints. Backed by Redis (shared across replicas)
# with a bounded in-memory fallback when Redis is unreachable.
_auth_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 10  # per window
_WINDOW_SECONDS = 60
_FALLBACK_MAX_KEYS = 10_000  # cap fallback memory under attack
_REDIS_RETRY_SECONDS = 30.0

_redis_client: object | None = None
_redis_failed_at: float = 0.0


def _get_redis():
    """Lazily connect to Redis; back off for a while after a failure."""
    global _redis_client, _redis_failed_at
    if _redis_client is not None:
        return _redis_client
    if time.time() - _redis_failed_at < _REDIS_RETRY_SECONDS:
        return None
    try:
        import redis

        client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        client.ping()
        _redis_client = client
        return client
    except Exception:
        _redis_failed_at = time.time()
        return None


def _over_limit_redis(client, client_ip: str) -> bool:
    # Fixed-window counter: one key per IP per window bucket.
    bucket = int(time.time() // _WINDOW_SECONDS)
    key = f"vf:auth_rl:{client_ip}:{bucket}"
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, _WINDOW_SECONDS * 2)
    count, _ = pipe.execute()
    return int(count) > _MAX_ATTEMPTS


def _over_limit_memory(client_ip: str) -> bool:
    now = time.time()
    window_start = now - _WINDOW_SECONDS
    if len(_auth_attempts) > _FALLBACK_MAX_KEYS:
        for ip in list(_auth_attempts):
            pruned = [t for t in _auth_attempts[ip] if t > window_start]
            if pruned:
                _auth_attempts[ip] = pruned
            else:
                del _auth_attempts[ip]
    attempts = [t for t in _auth_attempts.get(client_ip, []) if t > window_start]
    if len(attempts) >= _MAX_ATTEMPTS:
        _auth_attempts[client_ip] = attempts
        return True
    attempts.append(now)
    _auth_attempts[client_ip] = attempts
    return False


def auth_rate_limit_middleware():
    """Rate limiter for /auth/* endpoints (Redis-backed, in-memory fallback)."""

    async def _mw(request, call_next: Callable):
        if request.url.path.startswith("/auth/"):
            client_ip = request.client.host if request.client else "unknown"
            over_limit = False
            redis_client = _get_redis()
            if redis_client is not None:
                try:
                    over_limit = _over_limit_redis(redis_client, client_ip)
                except Exception:
                    global _redis_client, _redis_failed_at
                    _redis_client = None
                    _redis_failed_at = time.time()
                    over_limit = _over_limit_memory(client_ip)
            else:
                over_limit = _over_limit_memory(client_ip)
            if over_limit:
                return JSONResponse(
                    {"detail": "Too many requests. Please wait before trying again."},
                    status_code=429,
                    headers={"Retry-After": str(_WINDOW_SECONDS)},
                )
        return await call_next(request)

    return _mw
