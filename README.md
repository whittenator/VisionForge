# VisionForge

**A full-stack computer vision platform for teams who need to move from raw data to deployable model in hours, not days.**

VisionForge centralises dataset management, collaborative annotation, model training (YOLO via Ultralytics), active learning, and ONNX export into a single, auditable system — replacing the scattered collection of scripts and disjoint tools that most CV teams rely on today.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Service Endpoints](#service-endpoints)
- [API Overview](#api-overview)
- [Compute Clusters](#compute-clusters)
- [Running Tests](#running-tests)
- [Linting & Formatting](#linting--formatting)
- [Database Migrations](#database-migrations)
- [Observability](#observability)
- [Security Notes](#security-notes)
- [License](#license)

---

## Features

| Domain | Capabilities |
|---|---|
| **Dataset Management** | Ingest images/video, create versioned snapshots, full lineage tracking |
| **Annotation** | Keyboard-first annotator UX, bounding boxes, classification tags, configurable label schemas |
| **Training** | YOLO model training via Ultralytics, configurable hyperparameters, experiment tracking |
| **Active Learning** | Uncertainty sampling, high-value sample selection, automated retrain loops |
| **Model Registry** | Versioned artifacts, staging/production promotion, ONNX export with validation |
| **Compute Clusters** | Register external worker nodes, live CPU/RAM/disk/GPU telemetry (NVIDIA / AMD ROCm / CPU), pick an idle cluster when launching training or ONNX export |
| **RBAC** | Workspace-level roles: `viewer`, `annotator`, `developer`, `admin`, `owner` |
| **Async Jobs** | Celery-backed task queue with per-cluster routing; frontend polls job status with live progress |
| **Observability** | Prometheus metrics, Grafana dashboards, structured JSON logs with request IDs |
| **API-first** | Full REST API under `/api/`; automatable end-to-end via HTTP |

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐     ┌───────────┐
│  Browser    │────▶│  Frontend  (React 19 + Vite + TS)    │     │  MinIO    │
│  (React UI) │◀────│  :5173                               │     │  :9000    │
└─────────────┘     └──────────────────────────────────────┘     └─────▲─────┘
                                      │                                 │
                              REST / HTTP                               │
                                      │                                 │
                    ┌─────────────────▼────────────────────┐           │
                    │  Backend API  (FastAPI / Python 3.11) │───────────┘
                    │  :8000                                │
                    └──────┬──────────────────┬────────────┘
                           │                  │
                    ┌──────▼──────┐    ┌──────▼──────┐
                    │  PostgreSQL  │    │    Redis     │
                    │  + pgvector  │    │  (broker)    │
                    │  :5432       │    │  :6379       │
                    └─────────────┘    └──────┬───────┘
                                              │
                                       ┌──────▼──────┐
                                       │  Celery      │
                                       │  Worker(s)   │
                                       └─────────────┘
```

**Tech Stack**

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.112+, Python 3.11 |
| ORM / DB | SQLAlchemy 2.0+, PostgreSQL 17 + pgvector |
| Migrations | Alembic 1.13+ |
| Task Queue | Celery 5.3+ + Redis 7 |
| Object Storage | MinIO (S3-compatible) |
| ML / CV | Ultralytics (YOLO), PyTorch 2.3+, open-clip-torch, ONNX/ONNXRuntime |
| Frontend | React 19, Vite 5, TypeScript 5.9, React Router 6 |
| Styling | Tailwind CSS v4, class-variance-authority |
| Testing | pytest, Schemathesis, Playwright 1.48 |
| Observability | Prometheus, structlog (JSON), Grafana |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+ and Docker Compose v2
- (Local dev only) Python 3.11+ and Node.js 20+

---

## Quick Start

### Docker Compose — recommended

```bash
# 1. Clone the repo
git clone https://github.com/your-org/VisionForge.git
cd VisionForge

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum change all "change-me" values

# 3. Start all services
docker-compose up -d --build

# 4. Verify health
curl http://localhost:8000/health
```

The stack is ready when `/health` returns `{"status": "ok"}`.

**First login:** use the `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` values from your `.env`.

---

### Local Development (hot reload)

**Backend**

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Start supporting services only
docker-compose up -d postgres redis minio

# Run migrations
alembic upgrade head

# Start API server
uvicorn --app-dir src app.main:app --reload --port 8000
```

**Celery Worker**

```bash
# In a second terminal (same venv, backend/ directory)
celery -A app.jobs.celery_app:celery_app worker --loglevel=info
```

**Frontend**

```bash
cd frontend
npm install
npm run dev          # Vite dev server → http://localhost:5173

# If the backend runs on a non-default port:
VITE_API_URL=http://localhost:8001 npm run dev
```

> **Tip (WSL2 / port conflict):** if port 8000 is taken by `wslrelay.exe`, run the backend on `--port 8001` and set `VITE_API_URL` accordingly.

---

## Configuration

Copy `.env.example` to `.env` and set the following:

| Variable | Purpose | Default |
|---|---|---|
| `POSTGRES_HOST` | PostgreSQL host | `postgres` |
| `POSTGRES_DB` | Database name | `visionforge` |
| `POSTGRES_USER` | DB user | `visionforge` |
| `POSTGRES_PASSWORD` | DB password | **change-me** |
| `MINIO_ENDPOINT` | MinIO address | `minio:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `miniokey` |
| `MINIO_SECRET_KEY` | MinIO secret key | **change-me** |
| `S3_BUCKET` | Default storage bucket | `visionforge` |
| `REDIS_URL` | Celery broker URL | `redis://redis:6379/0` |
| `SECRET_KEY` | FastAPI session secret (≥32 chars) | **change-me** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | JWT refresh token TTL | `7` |
| `CORS_ALLOW_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:5173` |
| `SKIP_DB_MIGRATIONS` | Skip Alembic on startup | `false` |
| `SUPERUSER_EMAIL` | Seed admin email | `admin@visionforge.local` |
| `SUPERUSER_PASSWORD` | Seed admin password | **change-me** |
| `GRAFANA_ADMIN_USER` | Grafana admin username | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `admin` |
| `YOLO_BASE_MODEL` | Default YOLO base weights | `yolov8n.pt` |
| `MAX_TRAINING_EPOCHS` | Hard cap on training epochs | `300` |

---

## Service Endpoints

| Service | URL | Notes |
|---|---|---|
| Backend API | http://localhost:8000 | REST API |
| API Docs (Swagger) | http://localhost:8000/docs | Interactive OpenAPI UI |
| API Docs (ReDoc) | http://localhost:8000/redoc | |
| Health check | http://localhost:8000/health | |
| Metrics | http://localhost:8000/metrics | Prometheus scrape endpoint |
| Frontend | http://localhost:5173 | React SPA |
| Prometheus | http://localhost:9090 | |
| Grafana | http://localhost:3000 | Default: `admin` / env value |
| MinIO Console | http://localhost:9001 | Object storage UI |

---

## API Overview

All application routes are prefixed with `/api/`. Authentication routes are under `/auth/`.

| Prefix | Domain |
|---|---|
| `GET /health` | Health check |
| `GET /metrics` | Prometheus metrics |
| `/auth/` | Login, refresh, logout |
| `/api/workspaces/` | Workspace CRUD |
| `/api/projects/` | Project management |
| `/api/datasets/` | Dataset & version management |
| `/api/datasets/{id}/assets/` | Asset upload and retrieval |
| `/api/datasets/{id}/annotations/` | Annotation CRUD |
| `/api/experiments/` | Training experiment runs |
| `/api/artifacts/` | Model artifacts and ONNX export |
| `/api/jobs/` | Async job status polling |
| `/api/al/` | Active learning runs and items |
| `/api/rbac/` | Role management |
| `/api/ops/` | Admin / ops utilities |
| `/api/clusters/` | Compute cluster registration, live telemetry, heartbeat (agent-facing), availability selector |

Full interactive documentation is available at [`/docs`](http://localhost:8000/docs) when the server is running.

---

## Compute Clusters

VisionForge can dispatch training, evaluation, and ONNX export jobs to **registered compute clusters** (external worker nodes) rather than running everything on the API host. The `/clusters` page shows a live grid with per-cluster CPU, RAM, disk and GPU telemetry, OS info, and agent version. The training, evaluation, and ONNX export wizards include a cluster picker grouped by Available / Unavailable.

Registration is **discovery-based**: you install a `vf-agent` Docker container on the worker, and the platform reaches out to it to auto-detect hardware. No manual spec entry.

### Step 1 · Pick the worker's GPU vendor and run the installer

The agent ships as **three images**, one per GPU toolchain, because each needs a different PyTorch build:

| Vendor | Image tag | Base image |
|---|---|---|
| `nvidia` | `visionforge/agent:nvidia` | `pytorch/pytorch:2.10.0-cuda13.0-cudnn9-devel` |
| `rocm` | `visionforge/agent:rocm` | `rocm/pytorch:rocm7.2.3_ubuntu24.04_py3.12_pytorch_release_2.10.0` |
| `cpu` | `visionforge/agent:cpu` | `python:3.11-slim` |

The UI at **`/clusters/new`** asks you to pick the vendor and then shows a single `curl | bash` command (with a freshly-randomised token). The platform hosts the installer at `GET /api/agents/install.sh`:

```bash
curl -fsSL https://<platform>/api/agents/install.sh \
  | VF_AGENT_TOKEN=<random-secret> VF_VENDOR=nvidia bash
```

The script pulls the matching image, picks the correct GPU flags (`--gpus all` for NVIDIA; `/dev/kfd` + `/dev/dri` + `video`/`render` groups for ROCm; none for CPU), and starts the container with a persistent `vf-agent-state` volume. Override the host port with `VF_AGENT_PORT`, the image with `VF_AGENT_IMAGE`, or pass `REDIS_URL` through to the agent.

If you prefer to run `docker run` by hand, the equivalent for NVIDIA is:

```bash
docker run -d --name vf-agent \
  --restart unless-stopped \
  --gpus all \
  -p 9443:9443 \
  -v vf-agent-state:/var/lib/vf-agent \
  -e VF_AGENT_TOKEN=<random-secret> \
  -e REDIS_URL=redis://<platform-host>:6379/0 \
  visionforge/agent:nvidia
```

The agent exposes:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness check |
| `GET /info` | `Bearer $VF_AGENT_TOKEN` | Full hardware + OS snapshot used by discovery |
| `GET /telemetry` | `Bearer $VF_AGENT_TOKEN` | Live CPU/RAM/disk/GPU usage |
| `POST /adopt` | `Bearer $VF_AGENT_TOKEN` | Called once by the platform to assign `cluster_id` + `register_token` |

Until adoption, the agent does **not** start its Celery worker — it cannot pick up jobs.

### Step 2 · Register the cluster from the UI

At `/clusters/new`, enter:

- **Name** — display label.
- **Host** — IP or hostname reachable from the platform.
- **Port** — `9443` by default.
- **Workload kind** — `train`, `eval`, or `both`.

The agent token and the vendor you picked in Step 1 are sent automatically. On submit, the backend calls `GET /info` on the agent, **verifies the agent's reported `gpu_vendor` matches the vendor you selected**, creates the `Cluster` row populated from the response, then calls `POST /adopt` so the agent knows its `cluster_id`. The agent immediately starts a Celery worker subscribed to `cluster.{cluster_id}` and a heartbeat loop targeting the platform.

If the agent is unreachable, the API returns **`502 Bad Gateway`** with `[reason=connect|timeout|auth|bad_response]` appended to the detail; the UI surfaces a matching hint (e.g. "agent rejected the token"). A `[reason=vendor_mismatch]` means you installed the wrong vendor image for that box — reinstall using the image the agent actually reports.

### Selection rules

A cluster is **available** when:
- `enabled = true`
- `status = online`
- No `active_job_id` set (i.e., it is idle)
- Last heartbeat received within `90s`
- `kind` matches the requested workload (`kind = "both"` matches any)

If a selected cluster is no longer available at launch time, the relevant endpoint returns **`409 Conflict`**.

### API quick reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/clusters` | user | Full cluster list with telemetry, OS, agent metadata |
| `GET` | `/api/clusters/available?kind=train\|eval\|both` | user | Filtered list for the selector |
| `POST` | `/api/clusters/discover` | user | Probe a running agent and register the cluster |
| `GET` | `/api/clusters/{id}` | user | Single cluster detail |
| `PATCH` | `/api/clusters/{id}` | user | Update name / description / kind / enabled |
| `DELETE` | `/api/clusters/{id}` | user | Remove a cluster |
| `POST` | `/api/clusters/{id}/heartbeat` | **register_token** | Push telemetry (called by the agent) |
| `POST` | `/api/clusters/{id}/release` | user | Manually release a stuck reservation |
| `POST` | `/api/clusters/{id}/rotate-token` | user | Issue a new `register_token`; old one is invalidated |

### GPU vendors

| Vendor | Toolchain |
|---|---|
| `nvidia` | CUDA / `nvidia-smi` — recommended for YOLO training |
| `rocm` | AMD ROCm |
| `cpu` | No GPU — training will run on CPU and is significantly slower |

### Local development

To run the agent on the same Docker network as the platform for testing (the overlay builds the `cpu` image so it works on any host):

```bash
VF_AGENT_TOKEN=dev-agent-token \
  docker compose -f docker-compose.yml -f compose.agent.yml up -d agent
```

Then at `/clusters/new` pick the **CPU** vendor, and use host `agent`, port `9443`.

### Security

The agent's HTTP API is plain HTTP by default; deploy agents on a **private network or VPN**. The `scheme=https` option in the discover request is supported but you are responsible for terminating TLS in front of the agent.

Two tokens are involved:
- **`VF_AGENT_TOKEN`** — operator-supplied; the platform uses it to talk to the agent (`/info`, `/telemetry`, `/adopt`).
- **`register_token`** — platform-issued at discovery time; the agent uses it to heartbeat. Rotatable via `POST /api/clusters/{id}/rotate-token`.

---

## Running Tests

### Backend

```bash
source .venv/bin/activate

# Unit tests (no external services required)
pytest -q backend/tests/unit/

# Integration tests (requires running DB, Redis, MinIO)
pytest -q backend/tests/integration/

# Contract / property-based tests (requires running server)
pytest -q backend/tests/contract/

# Performance & regression tests
pytest -q backend/tests/perf/

# Unit tests with coverage report
pytest --cov=app --cov-report=term-missing backend/tests/unit/
```

Set `SKIP_DB_MIGRATIONS=1` to skip Alembic during test runs.

### Frontend

```bash
cd frontend

# Install Playwright browsers (first time only)
npx playwright install --with-deps

# All Playwright tests
npx playwright test

# Visual regression only
npx playwright test tests/visual/visual-check.spec.ts --project=chromium

# Run with visible browser
npx playwright test --headed
```

Visual regression artifacts (screenshots + console logs) are written to `frontend/test-results/visual/`.

---

## Linting & Formatting

Run all linters in one command:

```bash
chmod +x scripts/lint_all.sh
./scripts/lint_all.sh
```

Or run individually:

```bash
# Frontend
cd frontend
npm run lint        # ESLint
npm run format      # Prettier (auto-fixes)

# Backend
ruff check backend/src backend/tests
black --check backend/src backend/tests
black backend/src backend/tests      # auto-format
isort backend/src backend/tests
```

Key style rules:
- Python line length: **100** chars (black), **120** chars (ruff)
- Target Python: **3.11**
- Ruff rule sets: `E`, `F`, `I`, `UP`, `B` (`B008` ignored in `api/` files)
- TypeScript: single quotes, semicolons, 100-char print width

---

## Database Migrations

```bash
cd backend

# Generate a new migration from model changes
alembic revision --autogenerate -m "describe_change"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

Migration files live in `backend/src/app/db/migrations/versions/`. On startup, the app auto-runs `alembic upgrade head` unless `SKIP_DB_MIGRATIONS=1`.

---

## Observability

**Metrics** (`/metrics`): two Prometheus instruments are emitted per request:
- `vf_http_requests_total` — counter labelled by method, route, and HTTP status
- `vf_http_request_duration_seconds` — histogram of response times

**Logs**: all log lines are JSON (structlog), include a `request_id`, and are written to stdout. Use `structlog.get_logger()` — never `print()` or `logging.getLogger()`.

**Grafana**: dashboards are provisioned automatically from `deploy/grafana/provisioning/`. Open http://localhost:3000 after `docker-compose up`.

---

## Security Notes

The authentication stack is production-grade:

- **Password hashing**: `bcrypt` (work factor 12), via the maintained `bcrypt`
  library. Legacy SHA-256 hashes are rejected at login and must be reset.
- **Auth tokens**: signed JWTs (HS256) with separate access/refresh tokens and
  configurable TTLs (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`).
- **CORS origins**: configured via the `CORS_ALLOW_ORIGINS` env var
  (comma-separated). Restrict it to your actual domain(s) — do not leave the
  localhost defaults in production.
- **Auth rate limiting**: `/auth/*` endpoints are rate-limited per client IP.

Before going live, you still need to:

- **Rotate all `change-me` secrets** in `.env` (`SECRET_KEY`, DB / MinIO
  credentials, `SUPERUSER_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`). Never commit
  `.env`.
- **Harden the auth rate limiter**: it is currently in-memory (per-process), so
  it does not coordinate across multiple API replicas. Back it with Redis for a
  horizontally-scaled deployment.
- **Terminate TLS** in front of both the API and the cluster agents (the agent
  HTTP API is plain HTTP by default — keep agents on a private network/VPN).
- **Build the frontend for production** rather than shipping the Vite dev
  server (see [`frontend/Dockerfile.prod`](frontend/Dockerfile.prod)).

---

## License

Proprietary — all rights reserved. Contact the maintainers for licensing enquiries.
