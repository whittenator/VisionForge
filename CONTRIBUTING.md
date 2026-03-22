# VisionForge — Development Guide

Welcome, and thanks for contributing to VisionForge. This guide covers everything you need to set up a local development environment, understand the codebase conventions, write and run tests, and get your changes merged.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Repository Setup](#repository-setup)
- [Environment Configuration](#environment-configuration)
- [Running the Stack Locally](#running-the-stack-locally)
- [Project Structure](#project-structure)
- [Code Conventions](#code-conventions)
  - [Python / Backend](#python--backend)
  - [TypeScript / React / Frontend](#typescript--react--frontend)
- [Database Migrations](#database-migrations)
- [Writing Tests](#writing-tests)
- [Linting & Formatting](#linting--formatting)
- [Async Jobs (Celery)](#async-jobs-celery)
- [Observability](#observability)
- [Feature Specs](#feature-specs)
- [Pull Request Workflow](#pull-request-workflow)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Tool | Minimum Version | Notes |
|---|---|---|
| Git | 2.40+ | |
| Docker | 24+ | Docker Compose v2 included |
| Python | 3.11 | Use `pyenv` or system package |
| Node.js | 20 LTS | Use `nvm` or system package |
| npm | 10+ | Included with Node 20 |

---

## Repository Setup

```bash
git clone https://github.com/your-org/VisionForge.git
cd VisionForge

# Create a Python virtual environment at the repo root
python3.11 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# Install frontend dependencies
cd frontend && npm install && cd ..
```

---

## Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` and change every value marked `change-me`. The key variables for local development are:

```dotenv
POSTGRES_PASSWORD=<any local password>
MINIO_SECRET_KEY=<any local secret>
SECRET_KEY=<random string ≥32 chars>
SUPERUSER_EMAIL=admin@visionforge.local
SUPERUSER_PASSWORD=<any local password>
SKIP_DB_MIGRATIONS=false
```

See [README — Configuration](README.md#configuration) for the full variable reference.

---

## Running the Stack Locally

### Option A — Full Docker Compose (simplest)

```bash
docker-compose up -d --build
```

All services start together. The backend auto-runs migrations on first boot.

### Option B — Supporting services in Docker, code hot-reloaded locally

This is the recommended workflow for active development as it gives you instant feedback loops.

**Terminal 1 — Infrastructure**

```bash
docker-compose up -d postgres redis minio
```

**Terminal 2 — Backend API**

```bash
source .venv/bin/activate
cd backend
alembic upgrade head                            # run once, or after model changes
uvicorn --app-dir src app.main:app --reload --port 8000
```

**Terminal 3 — Celery Worker**

```bash
source .venv/bin/activate
cd backend
celery -A app.jobs.celery_app:celery_app worker --loglevel=info
```

**Terminal 4 — Frontend**

```bash
cd frontend
npm run dev       # Vite dev server on http://localhost:5173
```

> If port 8000 is already in use, start the backend on `--port 8001` and set
> `VITE_API_URL=http://localhost:8001` before running `npm run dev`.

---

## Project Structure

```
VisionForge/
├── backend/
│   ├── src/app/
│   │   ├── main.py              # FastAPI app: init, middleware, startup hooks
│   │   ├── api/                 # Route handlers — one file per domain
│   │   ├── models/              # SQLAlchemy ORM models (2.0 style)
│   │   ├── schemas/             # Pydantic v2 request / response schemas
│   │   ├── services/            # Business logic (routers delegate here)
│   │   ├── jobs/                # Celery app definition + task workers
│   │   ├── db/                  # Engine, session factory, Depends helpers, migrations
│   │   └── observability/       # Prometheus metrics + structlog configuration
│   ├── tests/
│   │   ├── unit/                # Service-level unit tests (no external services)
│   │   ├── integration/         # Full workflow tests (requires DB + services)
│   │   ├── contract/            # Schemathesis property-based API tests
│   │   └── perf/                # Performance & regression benchmarks
│   ├── requirements.txt         # Runtime dependencies
│   ├── requirements-dev.txt     # Test / lint / dev-only dependencies
│   ├── pyproject.toml           # black, ruff, isort, pytest configuration
│   └── alembic.ini              # Alembic migration settings
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # React entry point
│   │   ├── App.jsx              # Router + protected route wiring
│   │   ├── pages/               # Page components, grouped by feature
│   │   ├── components/
│   │   │   ├── ui/              # Primitive UI components (Button, Input, Card…)
│   │   │   ├── common/          # Composed components (EmptyState, ErrorState…)
│   │   │   └── layout/          # AppShell, ProtectedRoute
│   │   ├── services/            # api.ts, auth.ts, auth-store.tsx
│   │   ├── lib/utils.ts         # cn() helper, shared utilities
│   │   └── styles/globals.css   # Tailwind imports + OKLCH color tokens
│   └── tests/
│       ├── visual/              # Playwright visual regression snapshots
│       └── integration/         # Playwright end-to-end user flow specs
│
├── deploy/                      # Prometheus / Grafana / Postgres init configs
├── specs/                       # Feature specification documents
├── scripts/lint_all.sh          # Run all linters in one command
├── docker-compose.yml
├── .env.example
└── CLAUDE.md                    # AI assistant context (not for humans)
```

---

## Code Conventions

### Python / Backend

**General**

- Add `from __future__ import annotations` at the top of every module — enables deferred evaluation of type hints without runtime cost.
- Use absolute imports only — no relative imports (`from app.services.foo import ...` not `from ..services.foo import ...`).
- Never use `print()` or `logging.getLogger()`. Use `structlog.get_logger()` so every log line carries the request context automatically.

**Models (SQLAlchemy 2.0 style)**

```python
from __future__ import annotations
import uuid
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- Primary keys are **UUIDs** (`uuid.uuid4()`).
- All timestamps use `DateTime(timezone=True)`.

**Schemas (Pydantic v2)**

```python
from pydantic import BaseModel, ConfigDict

class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
```

Use `model_config = ConfigDict(from_attributes=True)` on any schema that reads from an ORM object.

**Services vs. Routers**

- All **business logic lives in services** (`app/services/`).
- Routers call services and translate results/exceptions to HTTP responses.
- Services raise **custom exceptions** (e.g., `ProjectNotFoundError`); routers catch these and raise `HTTPException`.

**DB Sessions**

Always inject via `Depends(get_db)` — never create sessions manually inside route handlers.

```python
from app.db.deps import get_db

@router.get("/projects/{id}")
async def get_project(id: uuid.UUID, db: Session = Depends(get_db)):
    return project_service.get(db, id)
```

**HTTP Exceptions**

```python
# In router — translate service errors to HTTP
try:
    project = project_service.get(db, project_id)
except ProjectNotFoundError:
    raise HTTPException(status_code=404, detail="Project not found")
```

---

### TypeScript / React / Frontend

**Components**

- Functional components only — no class components.
- New pages go in `src/pages/{feature}/{route}.tsx`.
- Use the `cn()` helper from `lib/utils.ts` to compose Tailwind class names.
- Use `cva` (class-variance-authority) for components with multiple visual variants.

```tsx
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("rounded font-medium", {
  variants: {
    variant: {
      primary: "bg-blue-600 text-white",
      ghost: "bg-transparent text-blue-600",
    },
  },
});

export function Button({ variant, className, ...props }) {
  return <button className={cn(buttonVariants({ variant }), className)} {...props} />;
}
```

**API Calls**

Use the typed helpers in `src/services/api.ts` — never `fetch()` directly.

```ts
import { apiGet, apiPost } from "@/services/api";

const project = await apiGet<Project>(`/api/projects/${id}`);
const created = await apiPost<Project>("/api/projects/", payload);
```

**Auth State**

Use `useAuth()` from `src/services/auth-store.tsx` — never read `localStorage` directly.

```tsx
import { useAuth } from "@/services/auth-store";

function Header() {
  const { user, logout } = useAuth();
  return <nav>{user?.email}</nav>;
}
```

**Styling**

- Tailwind v4 utility classes only.
- OKLCH color tokens are defined in `src/styles/globals.css` — prefer semantic tokens over raw color values.
- Do not write inline styles unless absolutely unavoidable.

---

## Database Migrations

Every change to an SQLAlchemy model **must** be accompanied by an Alembic migration.

```bash
cd backend
source ../.venv/bin/activate

# After changing a model, auto-generate the migration
alembic revision --autogenerate -m "add_label_status_to_asset"

# Review the generated file in backend/src/app/db/migrations/versions/
# Then apply it
alembic upgrade head

# Roll back one step if needed
alembic downgrade -1
```

**Rules:**
- Always review auto-generated migrations before committing — Alembic doesn't always get it right (e.g., column renames).
- Never hand-edit the `alembic_version` table directly.
- Do not squash migrations on shared branches.

---

## Writing Tests

### Backend — Arrange / Act / Assert

Follow the AAA pattern consistently:

```python
def test_create_project_returns_correct_name(db_session):
    # Arrange
    payload = ProjectCreate(name="My Project", workspace_id=workspace.id)

    # Act
    result = project_service.create(db_session, payload)

    # Assert
    assert result.name == "My Project"
```

**Test categories:**

| Directory | What it tests | Requires |
|---|---|---|
| `tests/unit/` | Service functions, pure logic | Nothing external |
| `tests/integration/` | Full DB-backed workflows | PostgreSQL, MinIO, Redis |
| `tests/contract/` | API schema conformance (Schemathesis) | Running server |
| `tests/perf/` | Response time budgets | Running server |

Set `SKIP_DB_MIGRATIONS=1` when running unit tests to skip the Alembic startup hook.

```bash
SKIP_DB_MIGRATIONS=1 pytest -q backend/tests/unit/
```

### Frontend — Playwright

Visual regression tests are **required for all UI changes**:

```bash
cd frontend

# Install browsers once
npx playwright install --with-deps

# Run visual regression suite
npx playwright test tests/visual/visual-check.spec.ts --project=chromium

# Inspect captured screenshots
ls frontend/test-results/visual/
```

Attach the generated screenshots and console logs to your PR description.

---

## Linting & Formatting

Run all linters before pushing:

```bash
./scripts/lint_all.sh    # exits 0 if everything passes
```

Individual commands:

```bash
# Backend
ruff check backend/src backend/tests          # fast linting
black --check backend/src backend/tests       # style check
black backend/src backend/tests               # auto-format
isort backend/src backend/tests               # import sorting

# Frontend
cd frontend
npm run lint      # ESLint (flat config)
npm run format    # Prettier (writes in place)
```

**CI blocks merges when linters fail.** Fix all issues locally before opening a PR.

Key configuration (from `backend/pyproject.toml`):
- Black line length: **100** chars
- Ruff line length: **120** chars
- Ruff rules: `E`, `F`, `I`, `UP`, `B`
- `B008` is suppressed in `api/` files (FastAPI `Depends()` in default args)

---

## Async Jobs (Celery)

Long-running operations (training, ONNX export, embedding generation, frame extraction) run as Celery tasks.

**Pattern:**

1. Router creates a `Job` row (`status = "queued"`) and enqueues the Celery task.
2. Task updates the row: `queued → running → succeeded | failed`.
3. Frontend polls `GET /api/jobs/{id}` until terminal state.

Task modules live in `backend/src/app/jobs/tasks/`. To add a new task:

```python
# backend/src/app/jobs/tasks/my_task.py
from app.jobs.celery_app import celery_app

@celery_app.task(name="my_task")
def run_my_task(job_id: str, **kwargs) -> None:
    # 1. Mark job running
    # 2. Do work
    # 3. Mark job succeeded or failed
```

Always update the `Job` row — the UI depends on it. Never swallow exceptions silently; set `status = "failed"` and store the error message.

---

## Observability

**Logging:** use structlog everywhere in the backend.

```python
import structlog
logger = structlog.get_logger()

logger.info("dataset.version_created", version_id=str(version.id), dataset_id=str(dataset.id))
```

All log lines are JSON and automatically include `request_id` from middleware context.

**Metrics:** the middleware in `api/middleware.py` records every request. If you add a new domain with custom instrumentation, follow the `vf_` prefix convention and use standard Prometheus types (Counter, Histogram, Gauge).

---

## Feature Specs

Significant features require a spec document before implementation begins. Create a new directory under `specs/` following the existing structure:

```
specs/
└── NNN-feature-slug/
    ├── spec.md        # What and why (non-technical, stakeholder-facing)
    ├── plan.md        # Implementation plan (technical design)
    ├── tasks.md       # Tasklist, updated as work progresses
    └── quickstart.md  # How to exercise the feature end-to-end
```

Reference the spec in your PR description so reviewers have context.

---

## Pull Request Workflow

1. **Branch** from `main` using a descriptive name: `feat/active-learning-ui`, `fix/onnx-export-timeout`.
2. **Develop** — keep commits focused and well-described.
3. **Self-review** the PR checklist below before requesting review.
4. **Open a PR** against `main` with a clear description of what changed and why.

### PR Checklist

- [ ] `./scripts/lint_all.sh` exits 0
- [ ] Relevant unit / integration tests are green (`pytest -q backend/tests/unit/`)
- [ ] If models changed, an Alembic migration is included
- [ ] If UI changed, Playwright visual regression screenshots are attached to the PR description
- [ ] If this is a significant feature, a spec doc exists in `specs/`
- [ ] No secrets, credentials, or `.env` files are committed
- [ ] No direct commits to `main` (feature branches only)

---

## Troubleshooting

**`alembic upgrade head` fails with "relation already exists"**
The DB was manually modified. Stamp the current head and re-run: `alembic stamp head`.

**Port 8000 already in use (WSL2)**
`wslrelay.exe` sometimes holds port 8000. Run the backend on `--port 8001` and set `VITE_API_URL=http://localhost:8001`.

**Playwright `browserType.launch` fails**
Browsers aren't installed. Run: `cd frontend && npx playwright install --with-deps`.

**`celery worker` can't connect to Redis**
Verify `REDIS_URL` in `.env` and that the Redis container is running: `docker-compose ps redis`.

**MinIO bucket missing on first run**
The backend creates the bucket on startup via the MinIO client. If it fails, check `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, and `MINIO_SECRET_KEY` in `.env`. Ensure `MINIO_DISABLED=false`.

**`pgvector` extension not found**
The `deploy/postgres/init/` directory contains the init SQL that enables the extension. If you're connecting to an external Postgres instance, run `CREATE EXTENSION IF NOT EXISTS vector;` manually.
