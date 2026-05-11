# Manual Testing Checklist — Web Revamp (003)

Walk this list before declaring Phase 5 (Validation) passed. Mark each item when verified.

## Environment
- [ ] `.env` configured (Postgres, MinIO, Redis, secrets)
- [ ] `docker-compose up -d --build` brings the stack up cleanly
- [ ] `GET /health` returns 200; `GET /metrics` returns Prometheus text

## Auth & Onboarding
- [ ] `POST /auth/signup` returns 201 and seeds the user's first workspace
- [ ] `POST /auth/login` returns 200 with access + refresh tokens
- [ ] Subsequent requests with the access token succeed; missing/invalid token returns 401
- [ ] Logging out via the AppShell button clears `vf_access_token` from localStorage

## Projects → Datasets → Versions
- [ ] Create a project (`POST /api/projects`) and see it on `/projects`
- [ ] Create a dataset (`POST /api/datasets/{projectId}`) under the project
- [ ] Initiate an upload (`POST /api/ingest/upload-url`); receive a presigned URL + `objectKey`
- [ ] Upload at least one image; per-file and batch progress visible in UI
- [ ] Snapshot creates a new dataset version

## Annotation
- [ ] Open the labeling workspace from a dataset
- [ ] Create a box, polygon, and keypoint annotation; each persists with version=1
- [ ] Update an annotation; the previous geometry is captured in history
- [ ] Concurrent edit: passing a stale `expected_version` returns a version conflict
- [ ] Container is keyboard-focusable (tabIndex=0), `role="application"`; aria-live status updates on save

## Experiments & Artifacts
- [ ] `POST /api/train` returns 202; `GET /api/jobs/{id}` transitions queued → running → succeeded
- [ ] Run detail view shows params + metrics
- [ ] Promote to model and `POST /api/export/onnx`; artifact appears with checksum + size; download works

## Collaboration & Audit
- [ ] Invite a user; accept invite; UI reflects role-based affordances
- [ ] Audit log records workspace, project, dataset, training, and export events

## Frontend (WCAG 2.1 AA spot checks)
- [ ] AppShell shows a single global header (`role="banner"`, single `<h1>` per page)
- [ ] Skip-to-content link is the first focusable element and targets `#main`
- [ ] Empty states for Projects, Datasets, Experiments, Artifacts each surface a primary CTA
- [ ] URL-persisted filters (e.g. `?projectId=`) restore on reload
- [ ] All form fields have associated labels; all icon-only buttons have `aria-label`

## Observability
- [ ] `vf_http_requests_total` and `vf_http_request_duration_seconds` populate Prometheus
- [ ] structlog JSON output includes `request_id` on every line
- [ ] Grafana dashboards reachable; no auth errors

## Performance & Regression
- [ ] API p95 < 200ms for core endpoints (`backend/tests/perf/test_api_perf.py`)
- [ ] Annotation create + update p95 < 100ms (`backend/tests/perf/test_annotation_perf.py`)
- [ ] ONNX export job completes within budget (`backend/tests/perf/test_onnx_regression.py`)

## Cleanup
- [ ] Archive the test project and delete test data
- [ ] `docker-compose down -v` removes containers and volumes
