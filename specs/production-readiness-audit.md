# VisionForge — Production Readiness Audit

**Date:** 2026-03-22
**Auditor:** Automated deep-analysis pass
**Branch:** `claude/audit-production-readiness-cQf1q`

---

## Executive Summary

VisionForge is architecturally sound and covers a wide feature surface (ingest, annotate, train, export, active learning, RBAC). However, prior to this audit **it was not deployable in a useful state** — four of the core workflows were either completely broken or inaccessible. This report documents every finding and the fixes applied.

| Category | Pre-audit | Post-fix |
|---|---|---|
| Docker Compose startup | Race-condition failure | Fixed (health checks) |
| Training pipeline | **Always failed** (0% success rate) | Fixed |
| Annotation flow | Dead link (404 on every click) | Fixed |
| Active Learning | No frontend (invisible to users) | Added full UI |
| Dataset versioning UI | Only one button, no history view | Added detail page |
| Metrics chart | Always empty (JSON unparsed) | Fixed |
| Hyperparameters | LR not sent to YOLO | Fixed |
| Augmentation controls | None exposed | Added (all YOLO params) |
| Dataset creation | Required manual URL construction | Added inline form |

---

## Part 1 — Critical Bugs (Fixed)

### 1.1 Training Always Failed
**File:** `backend/src/app/services/training_service.py`
**Severity:** P0 — 100% failure rate

`launch_training()` dispatched a Celery task but never created an `ExperimentRun` row in the database and never included `experimentId` in the task payload. The worker immediately raised:

```
ValueError: ExperimentRun None not found
```

on every invocation. No training run could ever succeed.

**Fix:** `training_service.py` now creates the `ExperimentRun` before dispatching, stores full params including `task` and `base_model`, and includes `experimentId` in the payload. `ops.py` now passes `name`, `baseModel`, and `current_user.id` to `launch_training()`.

---

### 1.2 Metrics Chart Always Empty
**File:** `backend/src/app/api/experiments.py:get_metrics()`
**Severity:** P1 — training progress invisible

The training worker stores metrics as:
```json
{"epochs": [{...}, {...}, ...]}
```

The `get_metrics` endpoint parsed this dict but fell into the `elif isinstance(data, dict): metrics = [data]` branch, returning `[{"epochs": [...]}]` instead of the epoch array. The frontend then found no `mAP50`, `box_loss`, etc. keys and rendered an empty chart.

**Fix:** Added explicit `if "epochs" in data` unwrapping branch.

---

### 1.3 `lr0` (Learning Rate) Not Forwarded to YOLO
**File:** `backend/src/app/jobs/tasks/training.py`
**Severity:** P1 — users set LR but YOLO used its default

The training form collected `learningRate` and sent it as `lr0` in `params`, but `model.train()` did not include `lr0=`. The YOLO trainer silently used its default `0.01`.

**Fix:** `model.train()` now passes `lr0`, `lrf`, `momentum`, `weight_decay`, `warmup_epochs`, and all augmentation parameters from `params`.

---

### 1.4 ANNOTATE Button Linked to Dataset ID (Dead Link)
**Files:** `frontend/src/pages/datasets/index.tsx:131`, `frontend/src/pages/projects/[projectId]/index.tsx:177`
**Severity:** P1 — annotator completely unreachable from the UI

Both "ANNOTATE" buttons linked to `/annotate/${ds.id}`, passing the **dataset UUID** as the `:assetId` route parameter. The annotator called `GET /api/assets/{datasetId}` which returned 404, leaving users stuck at "Error: Not Found".

**Fix:** Both links now point to `/datasets/${ds.id}/annotate`. A new `DatasetAnnotateGateway` component fetches the first unlabeled asset for the dataset's latest version and:
- Auto-redirects to `/annotate/:assetId` when there is exactly one asset
- Renders a prioritised asset picker when there are multiple assets
- Shows a clear empty state with upload CTA when no assets exist

---

## Part 2 — Missing Features (Implemented)

### 2.1 No Active Learning Frontend
**Files added:** `frontend/src/pages/active-learning/index.tsx`, `new.tsx`, `[alRunId].tsx`
**Severity:** P1 — entire AL workflow invisible

The backend (`/api/al/select`, `/api/al/runs`, `/api/al/runs/{id}/items`, `/api/al/runs/{id}/items/{id}/resolve`) was fully implemented but had zero frontend. Users had no way to trigger AL runs, browse selected items, or mark them resolved.

**Added:**
- **AL Runs list** (`/active-learning`) — lists all runs with strategy badge
- **New AL Run form** (`/active-learning/new`) — project + dataset version picker, strategy selector (uncertainty / diverse), sample count (k)
- **AL Run detail** (`/active-learning/:alRunId`) — shows all selected items with priority, progress bar, per-item ANNOTATE and RESOLVE buttons
- **Nav link** and home dashboard quick-access entry added

---

### 2.2 No Dataset Version History View
**Files added:** `frontend/src/pages/datasets/[datasetId]/index.tsx`
**Severity:** P1 — teams cannot see or compare dataset versions

The backend's `GET /api/datasets/{dataset_id}` returned all versions, but the only version UI was a bare "SNAPSHOT" button with no history display.

**Added:**
- Full **Dataset Detail page** at `/datasets/:datasetId` showing:
  - All versions in reverse chronological order with version number, asset count, locked status, notes, and timestamp
  - LATEST badge on the newest version
  - Per-version UPLOAD, ANNOTATE, and TRAIN links
  - Class map display
  - Dataset metadata panel
  - Snapshot creation with inline feedback
- Dataset names in the datasets list are now clickable links to this detail page
- "View all versions →" link in the snapshot page fixed to point here

---

### 2.3 No Dataset Creation UI
**File:** `frontend/src/pages/datasets/upload.tsx`
**Severity:** P1 — new users hit a dead end

The upload page required `?datasetId=...&versionId=...` query params but provided no way to create them. Teams had to reverse-engineer the API.

**Fix:** When `datasetId` / `versionId` are absent, the upload page now shows an inline **Create New Dataset** form: project selector + dataset name input → calls `POST /api/datasets/{projectId}` → auto-populates the IDs and continues to file selection.

---

### 2.4 No Augmentation Parameters in Training Form
**Files:** `frontend/src/pages/experiments/new.tsx`, `backend/src/app/jobs/tasks/training.py`
**Severity:** P2 — teams cannot customise augmentation strategy

The training form had only 4 hyperparameters (epochs, batch, imageSize, lr). YOLO supports a rich augmentation API.

**Added:**
- Collapsible **Augmentation Parameters** section exposing all standard YOLO augmentation knobs: `hsv_h`, `hsv_s`, `hsv_v`, `degrees`, `translate`, `scale`, `shear`, `flipud`, `fliplr`, `mosaic`, `mixup`, `copy_paste`
- Additional optimiser params: `lrf`, `momentum`, `weight_decay`, `warmup_epochs`
- All parameters forwarded to `model.train()` in the worker

---

## Part 3 — Infrastructure (Fixed)

### 3.1 docker-compose Race Conditions
**File:** `docker-compose.yml`
**Severity:** P1 — startup failure on most machines

`depends_on` without `condition: service_healthy` only waits for the container to start, not for the service to be ready. PostgreSQL commonly needs 3–10 seconds to initialise. The backend and worker frequently crashed on first startup with connection-refused errors.

**Fix:** Added `healthcheck` blocks to postgres (pg_isready), minio (HTTP live probe), and redis (redis-cli ping), then updated all `depends_on` to use `condition: service_healthy`.

Also added a comment noting the frontend runs Vite dev server — not suitable for production; nginx + build stage required.

---

## Part 4 — Remaining Known Issues (Not Fixed in This Pass)

These require larger changes or are known limitations documented for awareness.

### 4.1 Authentication Security (from CLAUDE.md)
- Token pattern `token-{user_id}` is a placeholder — replace with signed JWTs before production
- No automatic access-token refresh; sessions expire after 30 min without re-login
- CORS origins hardcoded to `localhost` — must be parameterised via env var for production

### 4.2 No Pagination on List Pages
All dataset, experiment, and artifact lists load unbounded. Will cause performance and browser memory issues beyond ~500 records. Requires server-side pagination added to API and frontend.

### 4.3 System Status Panel is Hardcoded
The home dashboard shows "● ONLINE" for API / QUEUE / STORAGE regardless of actual health. Wire to `GET /health` and a Celery inspect call.

### 4.4 LINEAGE Button Duplicates EXPORT ONNX
In `frontend/src/pages/artifacts/index.tsx` both EXPORT ONNX and LINEAGE buttons link to `/artifacts/export/${a.id}`. A separate lineage/provenance view showing the training run, dataset version, and parent model chain does not exist.

### 4.5 Model Artifact Download Missing
Trained PyTorch `.pt` models are stored in MinIO but there is no download button in the UI. Users cannot retrieve their model files without direct MinIO console access.

### 4.6 Uncertainty AL Strategy is Random
`backend/src/app/api/al.py:69` uses `random.random()` as a substitute for model confidence scores:
```python
scores = [random.random() for _ in assets]
```
This is documented in the code and works as a valid bootstrap strategy (random selection is reasonable before a model is trained). However, once a model artifact exists, the strategy should score assets by inference uncertainty.

### 4.7 No Video / Frame Extraction UI
`backend/src/app/jobs/tasks/frame_extraction.py` exists but no frontend triggers it. Teams uploading video datasets cannot extract frames through the UI.

### 4.8 Dataset Task Type Not Explicitly Tracked
Datasets have a `ClassMap` but no `task_type` field (detection vs classification). The training form asks the user to select task type independently, which can cause mismatches if the dataset was annotated for the wrong task. Recommend adding `task_type` to `Dataset` model.

### 4.9 Annotation Classes Not Pre-populated from Dataset
When opening the annotator, the class sidebar starts with only `["object"]`. The dataset's `ClassMap` classes are not loaded. Teams must manually re-add every class per session. Fix: `GET /api/datasets/:id` in the annotator on load.

### 4.10 No Test Coverage for New Code
Unit tests in `backend/tests/unit/` do not cover `training_service.py`, `al.py`, or any of the new frontend components.

---

## Part 5 — Deployment Checklist (docker-compose on local infra)

After fixes, a team **can** deploy with:

```bash
cp .env.example .env
# Fill: POSTGRES_*, MINIO_*, REDIS_URL, SECRET_KEY, FIRST_SUPERUSER_*
docker-compose up -d --build
```

Services will start in dependency order (postgres → minio/redis → backend → worker). Frontend is accessible at http://localhost:5173.

**Before going to production:**
- [ ] Replace auth tokens with signed JWTs
- [ ] Replace `SHA256` password hashing with bcrypt/argon2 (per CLAUDE.md note)
- [ ] Parameterise CORS origins via env var
- [ ] Replace Vite dev server with nginx serving a production build
- [ ] Add access-token refresh logic in `auth-store.tsx`
- [ ] Add Alembic migration for any new DB columns
- [ ] Enable HTTPS (reverse proxy or cert-manager)
- [ ] Add rate limiting on `/auth/` endpoints

---

## Part 6 — Feature Completeness Matrix

| Workflow | OD Support | Classification Support | Notes |
|---|---|---|---|
| Dataset upload | ✅ | ✅ | YOLO-format annotation files supported |
| Annotation (bounding box) | ✅ | — | Canvas-based, keyboard shortcuts, class management |
| Annotation (image classification) | — | ✅ | CLASSIFY mode in annotator, single-label per image |
| Dataset snapshots / versions | ✅ | ✅ | Version history now visible in detail page |
| Training — YOLO detect | ✅ | — | yolov8n/s/m/l/x, full YOLO format export |
| Training — YOLO classify | — | ✅ | Folder-per-class dataset structure built automatically |
| Training — hyperparameters | ✅ | ✅ | lr0, lrf, momentum, weight_decay, warmup |
| Training — augmentation | ✅ | ✅ | All YOLO aug params exposed, collapsible section |
| Metrics chart | ✅ | ✅ | mAP50, box_loss, cls_loss, precision, recall |
| Active learning — uncertainty | ✅ | ✅ | Random proxy scoring (pre-model bootstrap) |
| Active learning — diversity | ✅ | ✅ | Embedding-based coreset sampling |
| ONNX export | ✅ | ✅ | Via experiment detail → Export ONNX |
| Model artifact listing | ✅ | ✅ | Version number, type, size, run lineage |
| Model download | ❌ | ❌ | No direct download link (MinIO only) |
| Video / frame extraction | ❌ | ❌ | Backend task exists, no UI |
| Confusion matrix | ❌ | ❌ | Not implemented |
| Per-class metrics | ❌ | ❌ | Not implemented |
