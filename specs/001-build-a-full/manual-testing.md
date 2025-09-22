# Manual Testing Checklist

Use this checklist to validate the MVP manually before a release. Mark each item when verified.

## Environment
- [ ] .env configured (Postgres, MinIO, Redis, secrets)
- [ ] docker-compose stack starts (backend, worker, frontend, redis, minio, postgres, prometheus, grafana)

## Backend APIs
- [ ] Health: GET /health returns 200
- [ ] Metrics: GET /metrics returns Prometheus text
- [ ] Create project: POST /api/projects 201
- [ ] Presign upload: POST /api/ingest/upload-url 200
- [ ] Train job: POST /api/train 202 and job visible via GET /api/jobs/{id}
- [ ] ONNX export: POST /api/export/onnx 202 and completes

## Frontend (WCAG 2.1 AA spot checks)
- [ ] AppShell has skip link; focus visible on Tab; landmarks (banner/main) are present
- [ ] Admin Users: form fields have labels, buttons have accessible names
- [ ] Projects: empty state is announced and actionable
- [ ] Annotator: container focusable (tabIndex=0), role=application, aria-live status updates on save
- [ ] Keyboard-only: b/c/Enter/Arrow keys update state as described

## Jobs & Observability
- [ ] Job status transitions visible (queued → running → succeeded)
- [ ] Prometheus targets up; basic metrics visible
- [ ] Grafana dashboards reachable; no auth errors

## Performance & Regression
- [ ] API p95 under 200ms on local for core endpoints (see backend/tests/perf/test_api_perf.py)
- [ ] ONNX export regression passes (see backend/tests/perf/test_onnx_regression.py)

## Visual Verification
- [ ] Run Playwright visual sweep (chromium, 1440px)
- [ ] Archive artifacts: frontend/test-results/visual/*.png and *.console.log

## Sign-off
- Tester: ______________________  Date: __________
- Notes:
  - 
