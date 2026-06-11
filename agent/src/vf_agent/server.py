"""Agent HTTP server.

Endpoints (all gated by `Authorization: Bearer $VF_AGENT_TOKEN`):

- GET  /info        full hardware + OS snapshot used by the backend's discover flow
- GET  /telemetry   live CPU / RAM / disk / GPU usage (smaller payload, polled by backend)
- GET  /health      liveness check (no auth)
- POST /adopt       called once by the backend to assign cluster_id + register_token
"""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from vf_agent import __version__, discover, identity


class AdoptPayload(BaseModel):
    cluster_id: str
    register_token: str
    api_url: str


def _require_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("VF_AGENT_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent not configured (VF_AGENT_TOKEN unset)",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    presented = authorization.split(" ", 1)[1].strip()
    # Constant-time comparison to avoid leaking token bytes via timing.
    if not hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid agent token")


def build_app() -> FastAPI:
    app = FastAPI(title="VisionForge Agent", version=__version__)

    @app.get("/health")
    def health() -> dict[str, Any]:
        ident = identity.load()
        return {
            "ok": True,
            "version": __version__,
            "adopted": ident is not None,
            "cluster_id": ident.cluster_id if ident else None,
        }

    @app.get("/info", dependencies=[Depends(_require_token)])
    def info() -> dict[str, Any]:
        snapshot = discover.discover()
        snapshot["agent_version"] = __version__
        return snapshot

    @app.get("/telemetry", dependencies=[Depends(_require_token)])
    def telemetry() -> dict[str, Any]:
        snap = discover.discover()
        return {
            "cpu_usage_pct": snap["cpu_usage_pct"],
            "ram_used_mb": snap["ram_used_mb"],
            "disk_used_gb": snap["disk_used_gb"],
            "gpu_usage_pct": snap["gpu_usage_pct"],
            "gpus": snap["gpus"],
        }

    @app.post("/adopt", dependencies=[Depends(_require_token)])
    def adopt(payload: AdoptPayload) -> dict[str, Any]:
        identity.save(
            identity.Identity(
                cluster_id=payload.cluster_id,
                register_token=payload.register_token,
                api_url=payload.api_url.rstrip("/"),
            )
        )
        return {"ok": True, "cluster_id": payload.cluster_id}

    return app


app = build_app()
