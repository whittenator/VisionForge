from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.al import router as al_router
from app.api.datasets import router as datasets_router
from app.api.jobs import router as jobs_router
from app.api.middleware import logging_middleware
from app.api.ops import router as ops_router
from app.api.projects import router as projects_router
from app.observability.logging import configure_logging
from app.observability.metrics import metrics_middleware

configure_logging()
app = FastAPI(title="VisionForge API", version="0.0.1")

# Middlewares: metrics and logging
app.middleware("http")(metrics_middleware(app))
app.middleware("http")(logging_middleware())

app.include_router(projects_router)
app.include_router(datasets_router)
app.include_router(ops_router)
app.include_router(al_router)
app.include_router(jobs_router)

@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
