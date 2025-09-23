# Tasks: VisionForge Web Revamp

**Input**: Design documents from `/specs/003-visionforge-web-revamp/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md and design docs
2. Generate tasks by category with TDD ordering
3. Number tasks (T001, T002, ...), mark [P] where truly parallel
4. Validate dependencies and independence of [P] tasks
5. Execute: Setup → Tests → Core → Integration → Polish
```

## Phase 3.1: Setup
- [ ] T001 Confirm project structure per plan (web app with backend/ and frontend/) and ensure env files exist
- [ ] T002 Backend deps check: FastAPI, SQLAlchemy, Alembic present in `backend/pyproject.toml` and requirements files
- [ ] T003 Frontend deps check: React 19, Vite, Tailwind CSS 4 present in `frontend/package.json`
- [ ] T004 [P] Configure/verify linters: `ruff` for backend, ESLint/Prettier for frontend; add CI notes
- [ ] T005 [P] Add Playwright visual check note to PR process per Constitution (no code changes required)

## Phase 3.2: Tests First (TDD) — Contracts & Flows
- [ ] T006 [P] Contract test POST /auth/signup → `backend/tests/contract/test_auth_signup_post.py`
- [ ] T007 [P] Contract test POST /auth/login → `backend/tests/contract/test_auth_login_post.py`
- [ ] T008 [P] Contract test GET /projects → `backend/tests/contract/test_projects_get.py`
- [ ] T009 [P] Contract test POST /datasets → `backend/tests/contract/test_datasets_post.py`
- [ ] T010 [P] Contract test POST /datasets/{id}/uploads → `backend/tests/contract/test_dataset_uploads_post.py`
- [ ] T011 [P] Contract test GET /experiments/runs → `backend/tests/contract/test_runs_get.py`
- [ ] T012 [P] Contract test GET /experiments/runs/{runId} → `backend/tests/contract/test_run_detail_get.py`
- [ ] T013 [P] Contract test GET /artifacts/models → `backend/tests/contract/test_models_get.py`
- [ ] T014 [P] Contract test POST /artifacts/models/{modelId}/export → `backend/tests/contract/test_model_export_post.py`
- [ ] T015 [P] Integration test: signup → login → create project → list projects → `backend/tests/integration/test_onboarding_flow.py`
- [ ] T016 [P] Integration test: dataset upload flow (init session, upload sample files, create version) → `backend/tests/integration/test_upload_flow.py`
- [ ] T017 [P] Integration test: training run lifecycle (queue→running→done) → `backend/tests/integration/test_training_lifecycle.py`
- [ ] T018 [P] Integration test: promote to model and export → `backend/tests/integration/test_artifact_export.py`

## Phase 3.3: Core Implementation
### Backend Models (from data-model.md)
- [ ] T019 [P] Models: Workspace, Membership, Role enum → `backend/src/app/models/workspace.py`
- [ ] T020 [P] Models: User → `backend/src/app/models/user.py`
- [ ] T021 [P] Models: Project → `backend/src/app/models/project.py`
- [ ] T022 [P] Models: Dataset, ClassMap → `backend/src/app/models/dataset.py`
- [ ] T023 [P] Models: DatasetVersion, Asset, Annotation → `backend/src/app/models/dataset_version.py`
- [ ] T024 [P] Models: ExperimentRun → `backend/src/app/models/experiment.py`
- [ ] T025 [P] Models: ModelArtifact → `backend/src/app/models/artifact.py`
- [ ] T026 [P] Models: Invitation, AuditEvent, Notification → `backend/src/app/models/admin.py`

### Backend Services & Endpoints (from contracts)
- [ ] T027 Auth: POST /auth/signup → `backend/src/app/api/auth.py`
- [ ] T028 Auth: POST /auth/login → `backend/src/app/api/auth.py`
- [ ] T029 Projects: GET /projects → `backend/src/app/api/projects.py`
- [ ] T030 Datasets: POST /datasets → `backend/src/app/api/datasets.py`
- [ ] T031 Datasets: POST /datasets/{id}/uploads → `backend/src/app/api/datasets.py`
- [ ] T032 Experiments: GET /experiments/runs → `backend/src/app/api/experiments.py`
- [ ] T033 Experiments: GET /experiments/runs/{runId} → `backend/src/app/api/experiments.py`
- [ ] T034 Artifacts: GET /artifacts/models → `backend/src/app/api/artifacts.py`
- [ ] T035 Artifacts: POST /artifacts/models/{modelId}/export → `backend/src/app/api/artifacts.py`

### Frontend Shell & Critical Views
- [ ] T036 App shell: ensure single global header via `frontend/src/components/layout/AppShell.tsx`; add test note
- [ ] T037 Projects list page wired to GET /projects → `frontend/src/pages/projects/index.tsx`
- [ ] T038 Datasets upload page wired to POST /datasets and uploads → `frontend/src/pages/datasets/upload.tsx`
- [ ] T039 Experiments list/detail wired to runs endpoints → `frontend/src/pages/experiments/index.tsx`, `frontend/src/pages/experiments/new.tsx`
- [ ] T040 Artifacts list/export wired to artifacts endpoints → `frontend/src/pages/artifacts/index.tsx`, `frontend/src/pages/artifacts/export.tsx`

## Phase 3.4: Integration
- [ ] T041 DB session wiring and migrations for new models (Alembic) → `backend/`
- [ ] T042 RBAC enforcement middleware and decorators → `backend/src/app/api/`
- [ ] T043 Request/response logging, request IDs, and error handling filters → `backend/src/app/observability/`
- [ ] T044 CORS and security headers config → `backend/src/app/main.py`
- [ ] T045 Notifications: job completion events surfaced to UI (placeholder implementation) → `backend/src/app/services/`

## Phase 3.5: UX, Performance, and Polish
- [ ] T046 [P] Playwright visual checks for key routes (header uniqueness, empty states) → `frontend/tests/visual/*`
- [ ] T047 [P] Accessibility sweep (focus rings, ARIA, skip-to-content) → `frontend/src/components/`
- [ ] T048 [P] Performance guards: uploads and annotation responsiveness; simple benchmarks or timing asserts → `backend/tests/perf/`
- [ ] T049 [P] Unit tests for validation and error handling → `backend/tests/unit/`
- [ ] T050 Docs updates: api.md, manual-testing.md; update quickstart with any deltas → `specs/003-visionforge-web-revamp/`

## Dependencies
- T001–T005 before any tests
- T006–T018 (tests) must fail before starting T019+ (core)
- Models (T019–T026) before services/endpoints (T027–T035)
- Backend endpoints (T027–T035) before frontend wiring (T037–T040)
- Integration (T041–T045) after core endpoints exist
- Polish (T046–T050) after integration

## Parallel Execution Examples
- Launch in parallel after setup:
  - T006, T007, T008, T009, T010, T011, T012, T013, T014 (contract tests)
  - T015, T016, T017, T018 (integration tests) — ensure isolated data fixtures
- Core models in parallel: T019–T026 (distinct files)
- Polish tasks in parallel: T046–T050

---
*Generated from available artifacts: plan.md, data-model.md, contracts/openapi.yaml, research.md, quickstart.md*
