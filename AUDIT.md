# VisionForge — Platform Audit (Bugs & Production Readiness)

Date: 2026-06-09
Scope: full stack — backend API/services, Celery jobs, cluster agent, frontend, deployment/infra — measured against the target product: a streamlined web UI covering the full CV lifecycle (dataset curation → annotation → versioning → analysis → training → evaluation → model versioning → ONNX export).

All findings below were verified against the code at the referenced locations.

---

## 1. Executive Summary

The platform is further along than a typical prototype: annotation, dataset versioning/metrics, training with full hyperparameter + augmentation control, evaluation with per-class metrics/confusion matrices, model lineage, and ONNX export all work end-to-end from the UI. The biggest problems are:

1. **Authorization is broken at the object level.** Most resource endpoints never check workspace membership, and two job endpoints require no authentication at all. Any logged-in user can read/modify other workspaces' projects; anyone can read job status.
2. **The job/cluster lifecycle leaks on failure.** Broker enqueue failures are silently swallowed (job stays "queued" forever, cluster stays "busy" forever), and Celery has no time limits or `acks_late`, so a worker crash mid-training permanently wedges the job and its cluster.
3. **Several advertised lifecycle features are missing**: per-project MinIO/S3 storage selection, dataset duplicate detection / similarity search (pgvector is installed but unused), dataset improvement suggestions, an asset browse/filter UI, and checkpoint/resume for training.
4. **Deployment defaults are not production-safe**: Vite dev server in compose, weak fallback secrets, in-memory rate limiting, plain-HTTP agent communication, migrations auto-run by every replica.

---

## 2. Critical Bugs

### 2.1 Authorization / IDOR

| # | Location | Issue |
|---|---|---|
| C1 | `backend/src/app/main.py:156` | `GET /jobs/{job_id}/stream` (SSE) has **no auth dependency** — anyone can stream any job's status by guessing/leaking a job ID. |
| C2 | `backend/src/app/api/jobs.py:14` | `GET /api/jobs/{jobId}` has **no auth dependency** — same exposure as C1. |
| C3 | `backend/src/app/api/projects.py` (`get_project`, `update_project`) | No workspace-membership check: any authenticated user can read **and modify** any project (name, description, task_type). `list_projects` does filter by membership (lines 74–83), so the gap is specific to the detail/update endpoints. |
| C4 | `backend/src/app/api/workspaces.py` (`get_workspace`, `list_members`, `invite_member`) | Any authenticated user can read any workspace's metadata, enumerate its members (leaks emails + roles), and **invite themselves or others** into any workspace — a privilege-escalation path that defeats RBAC entirely. |
| C5 | `backend/src/app/api/datasets.py` (`get_dataset` and sibling asset/annotation routes) | Dataset/asset/annotation access is not validated against the owning project's workspace membership. |

**Fix direction:** add a shared `require_workspace_member(db, user, workspace_id, min_role=...)` dependency and apply it to every project/dataset/asset/annotation/experiment/artifact/job route, resolving the workspace via the resource's project. Job endpoints should authenticate and verify the job's project is visible to the caller.

### 2.2 Job / cluster lifecycle

| # | Location | Issue |
|---|---|---|
| C6 | `backend/src/app/services/training_service.py:109–119` | If `celery_app.send_task(...)` raises (broker down, Celery missing), the exception is swallowed and the API still returns `status: "queued"`. The Job row stays `queued` forever, the reserved cluster stays `busy` forever (its `active_job_id` was set at line 105), and the frontend polls indefinitely. Note `onnx_service.py` already does this correctly (releases cluster + fails job on dispatch error) — training should match it. |
| C7 | `backend/src/app/jobs/celery_app.py:45–52` | No `task_time_limit` / `task_soft_time_limit`, no `task_acks_late`, no `task_reject_on_worker_lost`. If a worker dies mid-task, the message is already acked → the task is never redelivered, `update_job_status` is never called, the job is stuck `running` and the cluster stuck `busy` with no recovery path. There is also no periodic sweeper to fail jobs/release clusters whose heartbeat/progress has gone stale. |

*Correction to an earlier internal finding:* cluster release **does** work on normal task completion — `jobs_service.update_job_status()` releases the cluster on any terminal status (`jobs_service.py:44–46`), and the training task reaches that on both success (`training.py:297`) and handled failure (`training.py:325`). The leaks are specifically (a) enqueue failure (C6) and (b) unhandled worker death (C7).

---

## 3. High-Severity Bugs

| # | Location | Issue | Fix |
|---|---|---|---|
| H1 | `backend/src/app/services/auth.py:16` | JWT `SECRET_KEY` falls back to a hardcoded default → token forgery in any deployment that forgets the env var. | Fail startup if `SECRET_KEY` is unset/default outside dev. |
| H2 | `backend/src/app/db/session.py:19`, `services/storage.py:45–46` | DB password defaults to `change-me`; MinIO credentials default to `minioadmin/minioadmin`. | Same fail-fast treatment as H1. |
| H3 | `backend/src/app/api/auth.py:116–133` | `/auth/refresh` mints a new access token **without checking the user still exists** (no DB lookup) — deleted/disabled users keep API access until refresh-token expiry. | Load the user by `user_id` and 401 if missing/disabled. |
| H4 | `backend/src/app/api/middleware.py:33–60` | Auth rate limiting is an in-process dict: useless across replicas, unbounded growth between prunes, racy. (Known limitation per CLAUDE.md, but it's a launch blocker for >1 replica.) | Redis-backed limiter. |
| H5 | `backend/src/app/services/dataset_service.py:50–51` | `snapshot_version()` counts **all** assets in the dataset, not the version's assets — locked version rows report inflated/incorrect `asset_count` as the dataset grows. Undermines trust in dataset version control. | Count assets scoped to the version being locked. |
| H6 | `backend/src/app/jobs/tasks/embeddings.py:108`, `db/session.py:8–10` | Embeddings are serialized as JSON into `Asset.meta_data`; the pgvector extension is registered but **no vector column exists**. Similarity search, duplicate detection, and embedding-based curation are impossible without a full-table Python scan. | Add `Asset.embedding: Vector(512)` + ivfflat/hnsw index, migrate, write vectors there. |
| H7 | `frontend/src/services/auth.ts:51–64`, `services/api.ts` | `refreshToken()` exists but is never called; on any 401 the client hard-logs the user out and redirects to login. Long annotation/training sessions will lose work context when the access token expires. | 401 interceptor: refresh once, retry, then logout. |
| H8 | `backend/src/app/api/al.py:310–313` | AL item resolution never sets `resolved_at` (model field exists) — breaks AL audit trail/metrics. | Set `resolved_at = datetime.now(timezone.utc)`. |
| H9 | `agent/src/vf_agent/server.py:35–39` + install path | Agent tokens travel over plain HTTP, and token comparison is not constant-time (`!=` instead of `hmac.compare_digest`). | `compare_digest`; document/require TLS or private-network for agents. |

---

## 4. Medium / Low Bugs

- **M1** `backend/src/app/jobs/tasks/training.py:312` — failure handler guards with `"ExperimentRun" in dir()`; this only works because the import at line 56 is function-local and only if execution got past it. If the task fails before line 56, the run row is never marked failed. Replace with a module-level import and drop the `dir()` check.
- **M2** `backend/src/app/main.py:74–81` — CORS allows all methods/headers with `allow_credentials=True`; tighten for production.
- **M3** `backend/src/app/api/auth.py:20–28` — no password length constraints on signup/login schemas (bcrypt 72-byte truncation is silent).
- **M4** `frontend/src/pages/experiments/[runId].tsx:240–245` — metrics polling continues every 3 s after the run reaches a terminal state; clear the interval when status leaves `running/queued`.
- **M5** `frontend/src/pages/evaluations/new.tsx:44–49` (and similar in artifacts/datasets pages) — `.catch(() => {})` silently swallows load failures, leaving forms with empty dropdowns and no error message.
- **M6** `frontend/src/pages/annotate/Annotator.tsx:686` — annotation delete removes the box from the canvas even if the server delete fails (silent desync).
- **M7** `backend/src/app/main.py:101–119` — migrations auto-run by every backend replica on startup; concurrent `alembic upgrade` across replicas can deadlock. Move to an init job and set `SKIP_DB_MIGRATIONS=1` on replicas.
- **M8** `agent/src/vf_agent/main.py:110–121` — supervisor exits the whole agent if any child (heartbeat/worker/server) dies; no respawn with backoff.
- **M9** `backend/src/app/api/clusters.py` heartbeat — `register_token` is sent in the JSON body rather than an `Authorization` header (more likely to be logged).
- **L1** Spelling drift `unlabelled` vs `unlabeled` between `models/asset.py:28` and `services/asset_service.py:74` — exact-match filters can silently miss assets.
- **L2** `backend/src/app/api/rbac.py:38–39` — superuser determined by env-var email comparison while `User.is_superuser` column exists unused.
- **L3** `/metrics`, `/docs`, `/openapi.json` are unauthenticated and proxied by `frontend/nginx.conf` — restrict in production.
- **L4** `docker-compose.yml` — no resource limits on any service; Prometheus/Grafana have no persistent volumes; Grafana's Postgres datasource uses `sslmode: disable` with a plaintext password.
- **L5** No React error boundary — any render exception white-screens the app.

---

## 5. Feature-Gap Matrix vs Target Product

| Lifecycle capability | Status | Notes |
|---|---|---|
| Upload images/video | ✅ end-to-end | Presigned PUT flow, per-file progress (`pages/datasets/upload.tsx`, `/api/ingest/upload-url`). |
| Browse/filter dataset assets | ⚠️ backend only | `/api/datasets/{id}/assets` filters by status/split/version, but there is **no gallery/browse UI** — only the annotate gateway. |
| Video frame extraction | ⚠️ backend only | Job + endpoint exist (`api/ops.py:144–194`); no UI trigger. |
| Annotation (box/polygon/keypoint/classification) | ✅ end-to-end | Full canvas editor with undo/redo, bulk save, optimistic locking, review queue. |
| Model-assisted prelabeling | ⚠️ backend only | Prelabel task exists; no UI to queue it (suggestions surface in review only). |
| Dataset version control | ✅ (with bug H5) | Snapshot/lock/version-scoped assets & metrics all work; snapshot counts are wrong. |
| Dataset analysis | ⚠️ partial | Class balance, coverage, geometry/resolution histograms, velocity: ✅ rich dashboard. **Missing:** duplicate detection, similarity search (blocked by H6), and any "suggested improvements" engine. |
| Storage selection (MinIO vs S3 per project) | ❌ not implemented | Single env-var-configured MinIO client (`services/storage.py`); no per-project/workspace config model, no boto3/AWS-credential path, no UI. |
| Training with hyperparameter + augmentation control | ✅ end-to-end | Schema-driven param groups incl. full augmentation set (mosaic, mixup, HSV, flips…), validated allow-list (`training/ultralytics_trainer.py`). |
| Live training view | ⚠️ partial | Per-epoch metrics persisted and charted, but via 3 s polling (plus M4 leak); no SSE/WebSocket push. Acceptable, not "live". |
| Checkpoint / resume | ❌ not implemented | Any interruption restarts from epoch 0. |
| Auto-eval on test split + post-hoc eval on chosen split | ✅ end-to-end | Per-class P/R/F1/AP, confusion matrix, mAP@50/95, FP/FN sample browser, threshold controls. |
| Model version control / registry | ✅ end-to-end | Artifacts with version/checksum/lineage tree (run → dataset version → class map → cluster → evals → siblings). |
| ONNX export | ✅ end-to-end | Opset/dynamic-axes options, onnxruntime validation, artifact row + download. |
| Active learning | ⚠️ partial | Uncertainty + diversity selection and resolve workflow work; no retraining feedback loop, `proposed_json` never populated, H8 bug. |
| Compute clusters | ✅ (with C6/C7 risks) | Discovery, heartbeats, per-cluster queues, live telemetry grid. |
| Admin / membership UI | ⚠️ partial | Members table read-only; invite flow stubbed in UI (and over-permissive on the backend, C4). |

---

## 6. Production Deployment Blockers (priority order)

1. **Object-level authorization** (C1–C5) — ship a workspace-membership dependency across all resource routers; authenticate job endpoints.
2. **Job/cluster failure handling** (C6, C7) — fail the job + release the cluster on enqueue error; add Celery `task_acks_late`, `task_reject_on_worker_lost`, time limits; add a stale-job sweeper that fails jobs and releases clusters after heartbeat/progress timeout.
3. **Fail-fast secrets** (H1, H2) — refuse to boot with default `SECRET_KEY` / DB / MinIO credentials outside dev mode.
4. **Production frontend + TLS** — compose currently ships the Vite dev server; wire `frontend/Dockerfile.prod` (nginx) into a prod compose/profile, terminate TLS in front of API and agents (H9).
5. **Redis-backed auth rate limiting** (H4) and migration init-job strategy (M7) before running >1 API replica.
6. **Token refresh on the frontend** (H3 + H7) — fix both halves together.

## 7. Recommended Roadmap to the Full-Lifecycle Vision

**Phase 1 — correctness & security (1–2 weeks):** items in §6, plus H5 snapshot counts, H8, M1–M6.
**Phase 2 — missing lifecycle features:** per-project storage backend (Workspace/Project `storage_config` + boto3 strategy + owner-only settings UI); pgvector embedding column + similarity/duplicate endpoints + dedup UI; asset gallery with filter/browse; UI triggers for frame extraction and prelabeling.
**Phase 3 — polish:** SSE/WebSocket live training metrics (the SSE job stream in `main.py` is a starting point — after C1 is fixed); checkpoint/resume; dataset "suggested improvements" (class-imbalance, low-coverage, duplicate-driven recommendations from existing metrics); AL retraining loop; admin invite flow with proper RBAC.
