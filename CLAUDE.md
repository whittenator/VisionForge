# VisionForge — CLAUDE.md

AI assistant context for the VisionForge repository. Read this before making changes.

---

## What Is VisionForge?

VisionForge is a full-stack computer vision platform for managing datasets, annotating images/video, training ML models (YOLO via Ultralytics), running active learning workflows, and exporting models to ONNX. It targets data-science and ML engineering teams.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.112+, Python 3.11 |
| ORM / DB | SQLAlchemy 2.0+, PostgreSQL 17 + pgvector |
| Migrations | Alembic 1.13+ |
| Task Queue | Celery 5.3+ with Redis 7 |
| Object Storage | MinIO (S3-compatible) |
| ML / CV | Ultralytics (YOLO), PyTorch 2.3+, open-clip-torch, ONNX/ONNXRuntime |
| Observability | Prometheus-client, structlog (JSON), Grafana |
| Frontend | React 19, Vite 5, TypeScript 5.9, React Router 6 |
| Styling | Tailwind CSS v4, class-variance-authority |
| E2E / Visual | Playwright 1.48 |
| Linting (FE) | ESLint 9, Prettier 3 |
| Linting (BE) | ruff, black, isort |

---

## Repository Layout

```
VisionForge/
├── backend/
│   ├── src/app/
│   │   ├── main.py              # FastAPI app init, middleware, startup
│   │   ├── api/                 # Route handlers (one file per domain)
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic v2 request/response schemas
│   │   ├── services/            # Business logic layer
│   │   ├── jobs/                # Celery app + task workers
│   │   ├── db/                  # Engine, session, deps, migrations
│   │   └── observability/       # Prometheus metrics + structlog setup
│   ├── tests/
│   │   ├── unit/                # Service-level unit tests
│   │   ├── integration/         # End-to-end workflow tests
│   │   ├── contract/            # Schemathesis property-based API tests
│   │   └── perf/                # Performance & regression tests
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml           # black, ruff, isort, pytest config
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # React entry point
│   │   ├── App.jsx              # Router + protected routes
│   │   ├── pages/               # Page components by feature
│   │   ├── components/
│   │   │   ├── ui/              # Primitive components (Button, Input, Card…)
│   │   │   ├── common/          # Composed components (EmptyState, ErrorState…)
│   │   │   └── layout/          # AppShell, ProtectedRoute
│   │   ├── services/            # api.ts, auth.ts, auth-store.tsx
│   │   ├── lib/utils.ts
│   │   └── styles/globals.css   # Tailwind imports + OKLCH color tokens
│   ├── tests/
│   │   ├── visual/              # Playwright visual regression snapshots
│   │   └── integration/         # Playwright user-flow specs
│   ├── package.json
│   ├── vite.config.ts
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   ├── .eslintrc.cjs
│   └── .prettierrc
├── deploy/
│   ├── prometheus/
│   ├── grafana/
│   └── postgres/
├── specs/                       # Feature specification docs
├── scripts/lint_all.sh          # Run all linters
├── docker-compose.yml
└── .env.example
```

---

## Running the Application

### Docker Compose (recommended)

```bash
cp .env.example .env     # fill in secrets
docker-compose up -d --build
```

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| MinIO console | http://localhost:9001 |

### Local Development (hot reload)

**Backend:**
```bash
cd backend
source ../.venv/bin/activate
uvicorn --app-dir src app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev          # Vite dev server on :5173
# Override API base: VITE_API_URL=http://localhost:8001 npm run dev
```

**Celery worker:**
```bash
cd backend
celery -A app.jobs.celery_app worker --loglevel=info
```

---

## Running Tests

### Backend

```bash
# All unit tests
pytest -q backend/tests/unit/

# Integration tests (requires running DB + services)
pytest -q backend/tests/integration/

# Contract tests (schemathesis, requires running server)
pytest -q backend/tests/contract/

# Performance tests
pytest -q backend/tests/perf/

# With coverage
pytest --cov=app --cov-report=term-missing backend/tests/unit/
```

Skip DB migrations during tests by setting `SKIP_DB_MIGRATIONS=1` or relying on the `PYTEST_CURRENT_TEST` env var check in `main.py`.

### Frontend

```bash
cd frontend
npx playwright test                                        # all tests
npx playwright test tests/visual/visual-check.spec.ts     # visual regression
npx playwright test --headed                               # with browser UI
```

---

## Linting & Formatting

Run all linters at once:
```bash
./scripts/lint_all.sh
```

Or individually:

```bash
# Frontend
cd frontend
npm run lint           # ESLint
npm run format         # Prettier (writes)

# Backend
ruff check backend/src backend/tests
black --check backend/src backend/tests
black backend/src backend/tests    # auto-format
isort backend/src backend/tests
```

Key settings (from `pyproject.toml`):
- Line length: **100** chars (black), **120** chars (ruff)
- Target Python: **3.11**
- Ruff rules: `E`, `F`, `I`, `UP`, `B`; `B008` ignored in `api/` files

---

## Database Migrations

```bash
# Create a new migration
cd backend
alembic revision --autogenerate -m "describe_change"

# Apply migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1
```

Migrations live in `backend/src/app/db/migrations/versions/`. On app startup, `main.py` can auto-run `alembic upgrade head` unless `SKIP_DB_MIGRATIONS=1`.

---

## Code Conventions

### Python (backend)

- **Type hints everywhere**: use `from __future__ import annotations` at the top of files; use `Mapped[T]` / `mapped_column()` for SQLAlchemy models (2.0 style).
- **Absolute imports** only — no relative imports.
- **Services layer** contains all business logic; routers delegate to services.
- **Pydantic v2** for schemas — use `model_config = ConfigDict(from_attributes=True)` when reading from ORM objects.
- **UUID primary keys**: generate with `uuid.uuid4()`, store as `UUID` column.
- **Timezone-aware timestamps**: always use `DateTime(timezone=True)`.
- **HTTP exceptions**: raise `HTTPException` in routers; raise custom exceptions (e.g., `EmailAlreadyExistsError`) in services and catch them in routers.
- **DB sessions**: inject with `Depends(get_db)` — never create sessions manually in routers.
- **Test isolation**: use `SKIP_DB_MIGRATIONS=1` in test environments; follow Arrange-Act-Assert (AAA) pattern.

### TypeScript / React (frontend)

- **Functional components only** — no class components.
- **File-based routing**: pages go in `src/pages/{feature}/{route}.tsx`.
- **API calls**: use the helpers in `src/services/api.ts` (`apiGet<T>()`, `apiPost<T>()`) — do not `fetch` directly.
- **Auth state**: use the `useAuth()` hook from `src/services/auth-store.tsx` — never read `localStorage` directly.
- **Component variants**: use `class-variance-authority` (`cva`) for variant logic; use `tailwind-merge` (`cn()`) when composing class names.
- **Styling**: Tailwind v4 utility classes only; OKLCH color tokens defined in `globals.css`.
- **Prettier config**: single quotes, semicolons, 100-char print width.

---

## Data Model (Key Entities)

```
User ──< Membership >── Workspace ──< Project ──< Dataset ──< DatasetVersion
                                                          └──< ClassMap
Project ──< ExperimentRun ──> Cluster
         ──< ModelArtifact
Dataset ──< Asset ──< Annotation
Project ──< ALRun ──< ALItem
Cluster (standalone — worker / agent telemetry)
```

- All PKs are UUIDs.
- Workspace membership uses a `Role` enum: `viewer | annotator | developer | admin | owner`.
- `Asset.label_status` tracks annotation progress.
- `ExperimentRun` stores `params` and `metrics` as JSON columns and an optional `cluster_id` FK recording which cluster ran the job.
- `Cluster` rows store static capacity (CPU / RAM / disk / GPU), live telemetry, a `kind` (`train | eval | both`), GPU `vendor` (`nvidia | rocm | cpu`), a `status` (`online | offline | busy | error`), an `enabled` flag, and a `register_token` used by the agent to authenticate heartbeats.
- Vector embeddings use pgvector (`pgvector` extension auto-registered in `session.py`).

---

## API Structure

- All routes are prefixed with `/api/` except auth (`/auth/`) and health (`/health`, `/metrics`).
- Router files: `api/auth.py`, `api/projects.py`, `api/datasets.py`, `api/experiments.py`, `api/artifacts.py`, `api/jobs.py`, `api/al.py`, `api/ops.py`, `api/rbac.py`, `api/clusters.py`.
- CORS is configured for `localhost:5173` and `127.0.0.1:5173` (update for production).

---

## Async Job Processing

Long-running operations (training, embedding generation, frame extraction, ONNX export) run as **Celery tasks** in `backend/src/app/jobs/tasks/`. Each task updates a `Job` row (status: `queued → running → succeeded | failed`). Frontend polls `/api/jobs/{id}` for status.

- Broker: Redis (`REDIS_URL` env var)
- Serialization: JSON
- Default queue: `default`
- Per-cluster queues: when a job is launched against a specific cluster, the task is routed to a dedicated queue named `cluster.{cluster_id}` so only that cluster's agent picks it up.

---

## Compute Clusters

VisionForge supports first-class **compute clusters** (worker nodes / agents) for routing training and evaluation jobs. Each cluster reports live resource telemetry via heartbeat so users can pick an idle, capable cluster when launching a job.

### Backend

- **Model**: `models/cluster.py` — `Cluster` table holds static capacity (CPU cores, RAM, disk, GPU vendor / count / model / memory), live telemetry (CPU/RAM/disk/GPU usage, per-GPU JSON breakdown), `kind` (`train | eval | both`), `status` (`online | offline | busy | error`), `enabled`, `active_job_id`, `register_token`, and `last_heartbeat_at`.
- **Schemas**: `schemas/cluster.py` — `ClusterCreate`, `ClusterUpdate`, `ClusterHeartbeat`, `Cluster`, `ClusterRegistration` (includes the `register_token`, returned only on creation), `ClusterSummary`, `ClusterHeartbeatAck`, plus `GpuInfo` for per-GPU telemetry.
- **Service**: `services/cluster_service.py` — handles CRUD, heartbeat ingestion with token auth, `is_available()` filtering (enabled + online + idle + fresh heartbeat + matches workload `kind`), `reserve_cluster()` / `release_cluster()`, and stale-heartbeat auto-degrade (`HEARTBEAT_TIMEOUT = 90s`).
- **Router**: `api/clusters.py` mounted at `/api/clusters`. The `POST /api/clusters/{id}/heartbeat` endpoint is **unauthenticated** (no user dependency) — the agent authenticates by including the cluster's `register_token` in the body.
- **Integration**: `services/training_service.py` and `services/onnx_service.py` accept an optional `cluster_id`. On launch they call `cluster_service.reserve_cluster()` (raising `ClusterNotAvailableError` → HTTP 409 if unavailable), persist `experiment_runs.cluster_id`, and route the Celery task to the `cluster.{cluster_id}` queue. `services/jobs_service.py` calls `release_cluster()` on terminal job status.
- **Migration**: `db/migrations/versions/0003_clusters.py` creates the `clusters` table and adds `experiment_runs.cluster_id` FK.

### Frontend

- **Pages**: `pages/clusters/index.tsx` (live grid polled every 5s with CPU/RAM/disk/GPU bars, vendor badges, heartbeat freshness) and `pages/clusters/new.tsx` (registration form that surfaces the agent install command and `register_token` exactly once).
- **Component**: `components/common/ClusterSelect.tsx` is the reusable selector grouped by Available / Unavailable, used by the training and ONNX export wizards.
- **Route**: `/clusters` and `/clusters/new`, with an `AppShell` nav entry "CLUSTERS".
- **API contract**: training (`/api/train`) and ONNX export (`/api/export/onnx`) accept an optional `clusterId` field; both return `409` if the chosen cluster is no longer available.

### Cluster Agent

The agent is an unattended daemon that runs on a worker machine. After registering a cluster in the UI, install the agent on the worker using the Docker command shown on the "Cluster registered" page — it embeds the cluster ID and `register_token` as env vars. The agent then POSTs telemetry to `/api/clusters/{id}/heartbeat` periodically (default expected cadence < 90s to stay "online").

---

## Observability

- **Metrics**: `vf_http_requests_total` (counter) and `vf_http_request_duration_seconds` (histogram) are incremented by `api/middleware.py`. Scraped at `/metrics`.
- **Logging**: structlog with JSON renderer. All log lines include `request_id` context. Use `structlog.get_logger()` — never `print()` or `logging.getLogger()` directly.
- **Grafana**: dashboards provisioned from `deploy/grafana/provisioning/`.

---

## Security Notes

- The current password hashing (`SHA256`) is a **placeholder for development only**. Replace with `bcrypt`/`argon2` before any production deployment.
- Auth tokens follow the pattern `token-{user_id}` — also a placeholder; replace with signed JWTs.
- CORS origins are hardcoded to localhost — parameterise via environment variable for production.

---

## Governance & PR Checklist

Before opening a PR:

1. **All linters pass**: `./scripts/lint_all.sh` exits 0.
2. **Tests pass**: relevant unit/integration tests green.
3. **UI changes require visual evidence**: run Playwright visual regression and attach screenshots to the PR description.
4. **No direct commits to `main`** — use feature branches.
5. **Migrations**: any model change must include an Alembic migration.
6. **Spec docs**: significant features should have a spec in `specs/` following the existing structure (`spec.md`, `plan.md`, `tasks.md`).

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Object storage |
| `MINIO_BUCKET` | Default storage bucket |
| `REDIS_URL` | Celery broker |
| `SECRET_KEY` | FastAPI session secret |
| `SKIP_DB_MIGRATIONS` | Set to `1` to skip Alembic on startup (tests) |
| `FIRST_SUPERUSER_EMAIL` / `FIRST_SUPERUSER_PASSWORD` | Seed admin user |
