from __future__ import annotations

import traceback
from typing import Callable

import structlog
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


def logging_middleware():
    async def _mw(request, call_next: Callable):
        logger.info("request:start", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised via integration
            logger.error("request:error", error=str(exc), tb=traceback.format_exc())
            return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        logger.info(
            "request:end",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response

    return _mw
