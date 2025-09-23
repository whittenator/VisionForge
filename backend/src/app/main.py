import os
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.al import router as al_router
from app.api.datasets import router as datasets_router
from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.experiments import router as experiments_router
from app.api.middleware import logging_middleware
from app.api.ops import router as ops_router
from app.api.projects import router as projects_router
from app.observability.logging import configure_logging
from app.observability.metrics import metrics_middleware
from app.services.auth import ensure_superuser
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
import time

configure_logging()
app = FastAPI(title="VisionForge API", version="0.0.1")

# Middlewares: metrics and logging
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _run_db_migrations():
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("script_location", "src/app/db/migrations")
    # Small retry loop in case DB isn't ready yet
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


_run_db_migrations()
ensure_superuser()

app.include_router(projects_router)
app.include_router(datasets_router)
app.include_router(ops_router)
app.include_router(al_router)
app.include_router(jobs_router)
app.include_router(auth_router)
app.include_router(experiments_router)

@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
