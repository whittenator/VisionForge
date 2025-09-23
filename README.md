# VisionForge

A full‑stack computer vision platform (MVP) built with FastAPI, Celery, Postgres/pgvector, Redis, MinIO on the backend and Vite + React + Tailwind v4 on the frontend. Tests-first and governance-driven with visual checks and performance guards.

## Features
- Projects, datasets, versions, and assets
- Annotation schemas and annotator UX (keyboard-first)
- Training, embeddings, active learning, and ONNX export (Celery jobs)
- Observability: Prometheus metrics and JSON structured logs
- Tests: contract, integration, unit, perf/regression, and Playwright visual checks

## Repository structure
```
backend/                 # FastAPI app, SQLAlchemy models, services, Celery tasks
  src/app/
  tests/
frontend/                # Vite + React + Tailwind v4 app
specs/                   # Project plan, research, data model, tasks and quickstart
scripts/                 # Helper scripts (lint, etc.)
deploy/                  # Prometheus/Grafana configs
```

## Quickstart
See `specs/001-build-a-full/quickstart.md` for detailed steps; below is a short version.

### Run with Docker Compose
1. Copy `.env.example` to `.env` and fill secrets (Postgres, MinIO, Redis, SUPERUSER credentials)
2. From repo root:
   - docker-compose up -d --build
3. Open:
   - Backend: http://localhost:8000/health
   - Frontend: http://localhost:5173/
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000

### Local development
- Backend (hot reload):
  - cd backend
  - source ../.venv/bin/activate
  - uvicorn --app-dir src app.main:app --reload --port 8000
- Frontend (Vite):
  - cd frontend
  - npm install
  - npm run dev

Tip: If port 8000 is busy (e.g., WSL2 wslrelay.exe), run the backend on 8001 and point the frontend at it:
- Backend:
  - cd backend && uvicorn --app-dir src app.main:app --reload --port 8001
- Frontend (set API URL for dev):
  - cd frontend
  - VITE_API_URL=http://localhost:8001 npm run dev

## Testing & Quality Gates
- Backend unit subset:
  - source .venv/bin/activate
  - pytest -q backend/tests/unit/test_services_*.py
- Performance & regression (local environment):
  - pytest -q backend/tests/perf/
- Visual checks (required for UI changes):
  - cd frontend && npx playwright test tests/visual/visual-check.spec.ts --project=chromium
  - Artifacts: `frontend/test-results/visual/*.png` and `*.console.log`

## Linting & Formatting
- Frontend: ESLint flat config and Prettier
  - cd frontend && npm run lint
- Backend: Ruff + Black
  - source .venv/bin/activate && pip install -r backend/requirements-dev.txt
  - ruff check backend/src backend/tests
  - black --check backend/src backend/tests
- All-in-one:
  - chmod +x scripts/lint_all.sh && ./scripts/lint_all.sh

## Governance
## PR Checklist (Frontend changes)

For any frontend change (components, pages, styles, routing), include in your PR description:
- Links to Playwright visual check evidence (screenshots at 1440px) for affected routes
- Console logs captured during navigation
- Notes on behavior validation vs. spec/acceptance criteria

Run the existing Playwright scripts locally before pushing:
- `npm run test:ui` (headless) or `npm run test:ui:headed` (headed)

## Troubleshooting
  - cd frontend && npx playwright install --with-deps

## License
Proprietary (adjust as needed).
