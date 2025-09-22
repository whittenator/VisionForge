# Tasks: Build a full-stack Computer Vision Platform (MVP)

**Input**: Design documents from `/specs/001-build-a-full/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
   → quickstart.md: Extract scenarios → integration tests
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → UX Consistency: shared components, a11y checks, design tokens
   → Performance: budgets, benchmarks, regression guards
   → Polish: unit tests, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness
```

## Format: `[ID] [P?] Description`
- [P]: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Phase 3.1: Setup
- [x] T001 Create repository structure (monorepo)
	Create directories: `/backend/src/app/{api,models,schemas,services,jobs,db,observability}`, `/backend/tests/{unit,integration,contract}`,
	`/frontend/src/{components,pages,services,styles}`, `/deploy/{prometheus,grafana}`, `/scripts`, `/migrations`.
- [x] T002 Add .env.example with required variables
	File: `/.env.example` (POSTGRES_*, MINIO_*, REDIS_URL, SECRET_KEY, S3_BUCKET, PROMETHEUS_PORT, GRAFANA_ADMIN_*, SUPERUSER_EMAIL/PASSWORD)
- [x] T003 Dockerize stack with docker-compose
	Files: `/docker-compose.yml`, `/backend/Dockerfile`, `/frontend/Dockerfile`, `/deploy/postgres/init/01_pgvector.sql`
	Compose services: postgres:17 (with pgvector), minio, redis, backend, worker, frontend, prometheus, grafana.
- [x] T004 Backend Python project scaffolding
	Files: `/backend/pyproject.toml` (deps: fastapi, uvicorn, pydantic>=2, sqlalchemy, alembic, psycopg2-binary, celery, redis,
	minio, prometheus-client, structlog, httpx, pytest, coverage, schemathesis, ultralytics, onnx, onnxruntime, open-clip-torch, torch, torchvision, pgvector`);
	`/backend/src/app/main.py` (FastAPI app, health, metrics route), `/backend/src/app/observability/logging.py` (JSON logging configuration).
- [x] T005 Database session and models baseline
	Files: `/backend/src/app/db/session.py` (SQLAlchemy engine/session from env), `/backend/src/app/db/base.py`, `/backend/alembic.ini` + `/backend/src/app/db/migrations/` (Alembic init).
- [x] T006 Initialize Alembic and pgvector extension
	Migration: create extension `vector`; baseline migration for core tables stub.
- [x] T007 Celery worker scaffolding
	Files: `/backend/src/app/jobs/celery_app.py` (Celery app, Redis broker), `/backend/src/app/jobs/tasks/__init__.py`.
- [x] T008 MinIO, Redis, and S3 clients
	Files: `/backend/src/app/services/storage.py` (MinIO presign/put/get), `/backend/src/app/services/cache.py` (Redis client factory).
- [x] T009 Observability stack configs
	Files: `/deploy/prometheus/prometheus.yml`, `/deploy/grafana/provisioning/{datasources,dashboards}`; add JSON logs via structlog in backend.
- [x] T010 Frontend scaffold
	Commands: initialize Vite React JS project in `/frontend`; add Tailwind + shadcn/ui; files: `/frontend/tailwind.config.js`, `/frontend/src/styles/globals.css`.
- [x] T011 Linting & formatting
	Files: `/backend/pyproject.toml` (ruff/black/isort config), `/frontend/.eslintrc.cjs`, `/frontend/.prettierrc`.

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
Contract tests (from `/contracts/openapi.yaml`)
- [x] T012 [P] Contract test: POST /api/projects → `backend/tests/contract/test_projects_post.py`
- [x] T013 [P] Contract test: POST /api/datasets/{projectId} → `backend/tests/contract/test_datasets_post.py`
- [x] T014 [P] Contract test: POST /api/ingest/upload-url → `backend/tests/contract/test_ingest_upload_url_post.py`
- [x] T015 [P] Contract test: POST /api/train → `backend/tests/contract/test_train_post.py`
- [x] T016 [P] Contract test: POST /api/export/onnx → `backend/tests/contract/test_export_onnx_post.py`
 - [x] T016a [P] Contract test: GET /api/jobs/{jobId} → `backend/tests/contract/test_jobs_get.py`

Integration tests (from user stories / quickstart)
- [x] T017 [P] Integration: project + dataset ingestion flow → `backend/tests/integration/test_ingest_flow.py`
- [x] T018 [P] Integration: training run (defaults, lineage recorded) → `backend/tests/integration/test_training_flow.py`
- [x] T019 [P] Integration: ONNX export validates vs reference → `backend/tests/integration/test_onnx_export.py`
- [x] T020 [P] Integration: active learning loop minimal (uncertainty/diversity) → `backend/tests/integration/test_active_learning_flow.py`

Frontend integration/UI tests
- [x] T021 [P] Playwright: annotator keyboard-first interactions → `frontend/tests/integration/annotator.spec.ts`
- [x] T022 [P] Playwright: admin creates users/roles → `frontend/tests/integration/admin_users.spec.ts`

## Phase 3.3: Core Implementation (ONLY after tests are failing)
Models (from data-model.md)
- [x] T023 [P] SQLAlchemy models: User, Membership → `/backend/src/app/models/{user.py,membership.py}`
- [x] T024 [P] SQLAlchemy models: Project → `/backend/src/app/models/project.py`
- [x] T025 [P] SQLAlchemy models: Dataset, DatasetVersion, Asset → `/backend/src/app/models/{dataset.py,dataset_version.py,asset.py}`
- [x] T026 [P] SQLAlchemy models: AnnotationSchema, Annotation, Track → `/backend/src/app/models/{annotation_schema.py,annotation.py,track.py}`
- [x] T027 [P] SQLAlchemy models: Experiment, Artifact → `/backend/src/app/models/{experiment.py,artifact.py}`
- [x] T028 [P] SQLAlchemy models: ALRun, ALItem → `/backend/src/app/models/{alrun.py,alitem.py}`
- [x] T029 [P] SQLAlchemy models: Job, Audit → `/backend/src/app/models/{job.py,audit.py}`
- [x] T030 Alembic migrations for all models + pgvector indexes → `/backend/src/app/db/migrations/*.py`

Schemas & Services
- [x] T031 [P] Pydantic v2 schemas for core entities → `/backend/src/app/schemas/*.py`
- [x] T032 Project & membership service → `/backend/src/app/services/project_service.py`
- [x] T033 Dataset & versioning service → `/backend/src/app/services/dataset_service.py`
- [x] T034 Ingestion & upload presign service (MinIO) → `/backend/src/app/services/ingest_service.py`
- [x] T035 Training service (Ultralytics wrapper) → `/backend/src/app/services/training_service.py`
- [x] T036 Embeddings service (OpenCLIP: DatologyAI/retr-opt-vit-b-32) → `/backend/src/app/services/embeddings_service.py`
- [x] T037 Active Learning service (uncertainty, diversity k-means using pgvector) → `/backend/src/app/services/active_learning_service.py`
- [x] T038 ONNX export & validation service → `/backend/src/app/services/onnx_service.py`

API Routers (from contracts)
- [x] T039 FastAPI router: POST /api/projects → `/backend/src/app/api/projects.py`
- [x] T040 FastAPI router: POST /api/datasets/{projectId} → `/backend/src/app/api/datasets.py`
- [x] T041 FastAPI router: POST /api/ingest/upload-url → `/backend/src/app/api/ops.py`
- [x] T042 FastAPI router: POST /api/train → `/backend/src/app/api/ops.py`
- [x] T043 FastAPI router: POST /api/export/onnx → `/backend/src/app/api/ops.py`
- [x] T044 Wire routers in app main → `/backend/src/app/main.py`
 - [x] T044a FastAPI router: GET /api/jobs/{jobId} → `/backend/src/app/api/jobs.py`

Jobs (Celery)
- [x] T045 Celery task: frame extraction (videos) → `/backend/src/app/jobs/tasks/frame_extraction.py`
- [x] T046 Celery task: prelabels via selected Artifact → `/backend/src/app/jobs/tasks/prelabels.py`
- [x] T047 Celery task: uncertainty scoring → `/backend/src/app/jobs/tasks/uncertainty.py`
- [x] T048 Celery task: embeddings generation (OpenCLIP) → `/backend/src/app/jobs/tasks/embeddings.py`
- [x] T049 Celery task: training run (Ultralytics) → `/backend/src/app/jobs/tasks/training.py`
- [x] T050 Celery task: ONNX export + validate → `/backend/src/app/jobs/tasks/onnx_export.py`

Frontend (MVP screens)
- [x] T051 [P] Vite/Tailwind/shadcn setup; design tokens and base layout → `/frontend/src/components/ui/*`, `/frontend/src/pages/_app.tsx`
- [x] T052 [P] Admin: users & roles management → `/frontend/src/pages/admin/users.tsx`
- [x] T053 [P] Projects: list/create → `/frontend/src/pages/projects/index.tsx`, `/frontend/src/pages/projects/create.tsx`
- [x] T054 [P] Datasets: upload & version snapshot → `/frontend/src/pages/datasets/{upload.tsx,version.tsx}`
- [x] T055 [P] Annotator: image (boxes) + classification tags, keyboard-first → `/frontend/src/pages/annotate/[assetId].tsx`
- [x] T056 [P] Experiments: launch training wizard, view runs → `/frontend/src/pages/experiments/{new.tsx,index.tsx}`
- [x] T057 [P] Artifacts: registry & ONNX export → `/frontend/src/pages/artifacts/{index.tsx,export.tsx}`
- [x] T058 [P] Dashboards: project home cards → `/frontend/src/pages/projects/[projectId]/index.tsx`

## Phase 3.4: Integration
- [x] T059 Configure Postgres (SQLAlchemy engine, Alembic) and ensure pgvector ready → `/backend/src/app/db/session.py`
- [x] T060 Configure MinIO client and bucket policies → `/backend/src/app/services/storage.py`
- [x] T061 Configure Redis + Celery (broker/result backend) → `/backend/src/app/jobs/celery_app.py`
- [x] T062 JSON structured logging with request IDs and Celery task IDs → `/backend/src/app/observability/logging.py`
- [x] T063 Prometheus metrics: FastAPI and Celery worker exports → `/backend/src/app/observability/metrics.py`
- [x] T064 Request/response logging & error handling middleware → `/backend/src/app/api/middleware.py`

## Phase 3.5: UX Consistency & Performance
- [x] T065 [P] UX: standard loading/empty/error/success components and usage sweep → `/frontend/src/components/common/*`
- [x] T066 [P] A11y: WCAG 2.1 AA pass on core screens (annotator/admin/projects)
- [x] T067 [P] Performance tests: API p95 < 200ms for core endpoints → `/backend/tests/perf/test_api_perf.py`
- [x] T068 [P] Regression guards: ONNX export validation vs reference metrics → `/backend/tests/perf/test_onnx_regression.py`

## Phase 3.6: Polish
- [x] T069 [P] Unit tests for services (training, embeddings, AL strategies) → `/backend/tests/unit/test_services_*.py`
   - Added: embeddings and active learning minimal tests → `/backend/tests/unit/test_services_embeddings.py`, `/backend/tests/unit/test_services_active_learning.py`
- [x] T070 [P] Update docs: `specs/001-build-a-full/quickstart.md` with screenshots/commands
- [x] T071 Remove duplication and run project-wide format/lint
- [x] T072 Manual testing checklist run and sign-off → `specs/001-build-a-full/manual-testing.md`

## Dependencies
- Setup (T001–T011) before tests and implementation
- Tests (T012–T022) must exist and fail before core implementation (T023+)
- Models (T023–T030) block services (T032–T038) which block routers (T039–T044)
- Celery app (T061) required before job tasks (T045–T050) execute
- Frontend scaffold (T051) before UI pages (T052–T058)

## Parallel Example
```
# Launch contract tests together (after setup):
Task: "Contract test: POST /api/projects" (backend/tests/contract/test_projects_post.py)
Task: "Contract test: POST /api/datasets/{projectId}" (backend/tests/contract/test_datasets_post.py)
Task: "Contract test: POST /api/ingest/upload-url" (backend/tests/contract/test_ingest_upload_url_post.py)
Task: "Contract test: POST /api/train" (backend/tests/contract/test_train_post.py)
Task: "Contract test: POST /api/export/onnx" (backend/tests/contract/test_export_onnx_post.py)
```

## Validation Checklist
- [x] All contracts have corresponding tests
- [x] All entities have model tasks
- [x] All tests come before implementation
- [x] Parallel tasks truly independent
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task
- [x] Performance tasks align with feature budgets
- [x] UX consistency tasks cover design system and a11y
