from __future__ import annotations

import asyncio
import json
import os
import time

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from app.api.al import router as al_router
from app.api.artifacts import router as artifacts_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.experiments import router as experiments_router
from app.api.jobs import router as jobs_router
from app.api.middleware import auth_rate_limit_middleware, logging_middleware
from app.api.ops import router as ops_router
from app.api.projects import router as projects_router
from app.db.deps import get_db
from app.models.job import Job as JobModel
from app.observability.logging import configure_logging
from app.observability.metrics import metrics_middleware
from app.services.auth import ensure_superuser
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

# Import new routers (created by the new API implementation)
try:
    from app.api.annotations import router as annotations_router
    _has_annotations = True
except ImportError:
    _has_annotations = False

try:
    from app.api.assets import router as assets_router
    _has_assets = True
except ImportError:
    _has_assets = False

try:
    from app.api.workspaces import router as workspaces_router
    _has_workspaces = True
except ImportError:
    _has_workspaces = False

configure_logging()
app = FastAPI(
    title="VisionForge API",
    version="1.0.0",
    description="Computer vision platform API — dataset management, annotation, training, and model export.",
)

# Middlewares (order matters: outermost = last added)
app.middleware("http")(auth_rate_limit_middleware())
app.middleware("http")(metrics_middleware(app))
app.middleware("http")(logging_middleware())

# CORS: allow frontend origin for local dev and compose
_cors_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


def _alembic_paths():
    """Return absolute paths for alembic.ini and migration script_location."""
    app_dir = os.path.dirname(__file__)
    backend_root = os.path.abspath(os.path.join(app_dir, "..", ".."))
    alembic_ini = os.path.join(backend_root, "alembic.ini")
    migrations_dir = os.path.join(app_dir, "db", "migrations")
    return alembic_ini, migrations_dir


def _should_init_db() -> bool:
    if os.getenv("SKIP_DB_MIGRATIONS", "false").lower() == "true":
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _run_db_migrations():
    alembic_ini, migrations_dir = _alembic_paths()
    cfg = AlembicConfig(alembic_ini)
    cfg.set_main_option("script_location", migrations_dir)
    attempts = 0
    while True:
        try:
            alembic_command.upgrade(cfg, "head")
            break
        except Exception as e:  # pragma: no cover
            attempts += 1
            if attempts >= 10:
                raise e
            time.sleep(2)


if _should_init_db():
    _run_db_migrations()
    ensure_superuser()

# Core routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(datasets_router)
app.include_router(ops_router)
app.include_router(al_router)
app.include_router(jobs_router)
app.include_router(experiments_router)
app.include_router(artifacts_router)

# New feature routers (conditionally registered based on availability)
if _has_annotations:
    app.include_router(annotations_router)
if _has_assets:
    app.include_router(assets_router)
if _has_workspaces:
    app.include_router(workspaces_router)

try:
    from app.api.evaluation import router as evaluation_router
    app.include_router(evaluation_router)
except ImportError:
    pass


@app.get("/health", tags=["ops"])
def health():
    return JSONResponse({"status": "ok", "version": "1.0.0"})


@app.get("/metrics", tags=["ops"])
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/api/jobs/{job_id}/stream", tags=["jobs"])
async def stream_job_status(job_id: str, db: Session = Depends(get_db)):
    """Server-Sent Events endpoint for real-time job status updates.

    Connect with EventSource in the browser:
      const es = new EventSource(`/api/jobs/${jobId}/stream`);
      es.onmessage = (e) => { const data = JSON.parse(e.data); ... };
    """

    async def event_generator():
        last_payload: dict | None = None
        for _ in range(240):  # max 4 minutes
            job = db.get(JobModel, job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                break
            payload = {
                "id": job.id,
                "type": job.type,
                "status": job.status,
                "progress": round(job.progress, 4),
            }
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n"
                last_payload = payload
            if job.status in ("succeeded", "failed"):
                yield f"data: {json.dumps({**payload, 'done': True})}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
