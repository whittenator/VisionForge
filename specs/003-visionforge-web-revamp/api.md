# API Reference — Web Revamp (003)

This spec's API surface is pinned by the OpenAPI document at
[`contracts/openapi.yaml`](./contracts/openapi.yaml). The notes below are a
quick index — the OpenAPI document is the source of truth.

## Endpoint Map

| Resource | Method + Path | Purpose | Status |
|---|---|---|---|
| Auth | `POST /auth/signup` | Create account + first workspace | 201 |
| Auth | `POST /auth/login` | Email/password → access + refresh tokens | 200 |
| Auth | `POST /auth/refresh` | Exchange refresh for new access token | 200 |
| Auth | `POST /auth/logout` | Revoke current session | 204 |
| Projects | `GET /api/projects` | List projects in the workspace | 200 |
| Projects | `POST /api/projects` | Create project | 201 |
| Datasets | `GET /api/datasets` (`?project_id=…`) | List datasets, optionally filtered by project | 200 |
| Datasets | `POST /api/datasets/{projectId}` | Create dataset under project | 201 |
| Datasets | `POST /api/datasets/{datasetId}/snapshot` | Snapshot a new version | 201 |
| Datasets | `POST /api/datasets/{datasetId}/import` | Import COCO/YOLO/Datumaro | 201 |
| Ingest | `POST /api/ingest/upload-url` | Get a presigned PUT URL + object key | 200 |
| Ingest | `POST /api/ingest/confirm` | Confirm an uploaded asset | 201 |
| Annotations | `POST /api/annotations` | Create annotation (box/polygon/keypoint/classification) | 201 |
| Annotations | `PUT /api/annotations/{id}` | Update with optimistic version lock | 200 |
| Annotations | `DELETE /api/annotations/{id}` | Delete annotation | 204 |
| Annotations | `GET /api/annotations/{id}/history` | Version history for an annotation | 200 |
| Experiments | `GET /api/experiments/runs` | List training runs | 200 |
| Experiments | `GET /api/experiments/runs/{runId}` | Run detail (params + metrics) | 200 |
| Train | `POST /api/train` | Launch a training job | 202 |
| Artifacts | `GET /api/artifacts/models` | List model artifacts | 200 |
| Artifacts | `POST /api/artifacts/models/{id}/export` | Export to ONNX | 202 |
| Jobs | `GET /api/jobs/{id}` | Poll job status (queued/running/succeeded/failed) | 200 |
| Ops | `GET /health` | Liveness check | 200 |
| Ops | `GET /metrics` | Prometheus exposition | 200 |

## Conventions

- All UUIDs use string form. Timestamps are ISO 8601 with an explicit UTC offset
  (`+00:00`), produced by Python's `datetime.isoformat()` on timezone-aware values
  — e.g. `"2026-05-10T13:55:43.123456+00:00"`.
- Authentication uses a bearer token from `/auth/login` in the `Authorization: Bearer …`
  header. Refresh via `POST /auth/refresh`.
- `Job`-returning endpoints (train, export) respond `202` with a `{id, status}` payload;
  poll `/api/jobs/{id}` until `status` is `succeeded` or `failed`.
- Errors follow FastAPI's default shape: `{ "detail": "..." }`. Validation failures use
  `422` with field-level error detail.
- Optimistic locking on annotations: pass `expected_version` on `PUT`; a mismatch returns
  `409 VersionConflictError`.

## Performance Budgets

| Path | Budget |
|---|---|
| Core API endpoints (POST /api/projects, /api/ingest/upload-url) | p95 < 200ms |
| Annotation create + update (service-level) | p95 < 100ms |
| Upload presign (service-level, MinIO disabled) | p95 < 50ms |
| ONNX export job | completes within ~2s in test mode |

These budgets are enforced by tests in `backend/tests/perf/`.
