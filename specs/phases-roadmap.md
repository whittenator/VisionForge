# VisionForge — Post-Foundation Phases Roadmap

**Date:** 2026-05-09
**Branch:** `claude/visionforge-phases-review-M94dh`
**Context:** PR #9 (cluster management) and PR #10 ("Phase 1 — annotator, evaluation, inference, datumaro, bcrypt-only") are merged into `main`. This document tracks the remaining gaps between the comprehensive product plan and the current implementation, grouped into phases. Naming continues from the user's PR #10 ("Phase 1") — so this doc covers Phases 2 → 5.

---

## Audit Summary (against the comprehensive product plan)

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | Teams / workspaces / RBAC | ✅ | `models/workspace.py`, `api/rbac.py` |
| 2 | Project + task wizard | ⚠️ | only a simple create-form — no multi-step flow |
| 3 | Dataset import (Datumaro) | ✅ | COCO/YOLO native + Datumaro fallback |
| 4 | Annotation pipeline | ✅ | bbox/polygon/keypoint/classify, undo/redo, hotkeys, optimistic lock |
| 5 | Annotation quality control | ❌ | no review queues, no consensus, no error mining |
| 6 | Dataset versioning | ✅ | snapshots, lock, version list |
| 7 | Evaluation | ✅ | first-class job, confusion matrix, FP/FN viewer |
| 8 | Active learning | ✅ | uncertainty + diverse coreset |
| 9 | Model training | ✅ | per-cluster routing, full hyperparams + augmentation |
| 10 | Model artifacts | ⚠️ | no `.pt` download endpoint, no real lineage view |
| 11 | Inference | ✅ | LRU cache, `/predict`, bbox overlay UI |
| 12 | Compute clusters | ✅ | NVIDIA + ROCm + CPU, train/eval routing, telemetry, picker |
| 13 | Observability | ✅ | Prometheus + structlog + request_id; Grafana provisioning present |
| 14 | Auth / security | ✅ | bcrypt + JWT + rate limiting; MFA/SSO deferred per spec |
| 15 | Frame extraction | ✅ | Celery task + presigned-URL frames; **UI trigger not surfaced** |
| 16 | Plugin / extensibility | ❌ | no registry for trainers / task types |

**Cluster requirements** (CPU/RAM/disk/GPU telemetry, NVIDIA+ROCm vendor support, train+eval selection, agent heartbeat) are 5.5/6 met. The single gap is the **ONNX export form has no cluster picker UI** (the backend already accepts `clusterId`).

---

## Phase 2 — Annotation & Dataset Polish

Focus: close gaps in the data-entry path that block labelling teams.

1. **Multi-step project / task wizard**
   - New `/projects/new` flow: task type (detect/classify) → class definition → default dataset settings → import option (skip / upload / Datumaro).
   - Persist `task_type` on the `Project` *and* on `Dataset` (`Dataset.task_type` column + Alembic migration) so training can validate dataset-task compatibility.
2. **Annotator bulk-save** *(carried over from PR #10 caveats)*
   - Replace per-annotation `PUT` with a single `POST /api/annotations/bulk` that accepts an array of {id, version, payload} and returns per-row 200 / 409.
3. **Pre-populate classes from `ClassMap`**
   - On annotator load, `GET /api/datasets/{id}` and seed the class sidebar instead of starting from `["object"]`.
4. **Annotation quality control (MVP)**
   - `Annotation.review_status` enum (`unreviewed | approved | rejected`) + reviewer assignment.
   - `/datasets/{id}/review` queue page: filter by status, approve / reject / send back, with diff vs. previous version.
   - Optional consensus mode: assign N annotators to the same asset, surface disagreement.
   - Error mining: nightly Celery task that runs the latest model over labelled assets and flags annotations whose IoU vs. prediction is below a threshold.
5. **Pagination on list pages** (datasets, experiments, artifacts, evaluations, AL runs)
   - Server-side `?page=&page_size=` + `X-Total-Count`; frontend pager component.

**Exit criteria:** a new team can land on the home page, click "New Project", and reach a labelled, reviewed dataset version without ever needing to construct a URL by hand.

---

## Phase 3 — Model Lifecycle Polish

Focus: make trained models discoverable, downloadable, and traceable.

1. **`.pt` model download**
   - `GET /api/artifacts/models/{id}/download` → presigned MinIO GET URL (or streaming `FileResponse` for small artifacts).
   - DOWNLOAD button on `/artifacts` row (next to PREDICT / EXPORT ONNX).
2. **Real lineage view** (replaces the duplicate LINEAGE button)
   - `/artifacts/{id}/lineage` page: training run → dataset version → parent class map → evaluations using this artifact, all with deep links.
3. **ONNX export form: cluster picker**
   - Add `<ClusterSelect kind="train">` to `frontend/src/pages/artifacts/export.tsx`; pass `clusterId` in the POST body.
4. **System status panel wired to reality**
   - Replace the hardcoded `● ONLINE` badges with calls to `/health` and a Celery-inspect endpoint.
5. **Frame extraction UI**
   - Surface the existing backend task in the dataset upload page — "this is a video, extract frames at N fps" toggle.
6. **Detection mAP@[.5:.95]** *(carried over from PR #10 caveats)*
   - Extend `EvaluationService` to compute mAP averaged across IoU thresholds in 0.05 steps, stored alongside the existing single-IoU number.

**Exit criteria:** a developer can trace any deployed model back to the exact dataset version + run + evaluation, download the weights, and re-run an evaluation against new data.

---

## Phase 4 — Production Inference & Scale

Focus: scale beyond a single backend container and start treating inference as a real product surface.

1. **Triton serving front-end** *(carried over from PR #10 caveats)*
   - Optional `INFERENCE_BACKEND=triton` mode where `/predict` proxies to a Triton container. Auto-generate Triton model repo layout from a `ModelArtifact` (config.pbtxt + ONNX engine).
   - Cluster table grows a `kind=infer` option and an `inference_url` column.
2. **Plugin registry**
   - `app/plugins/registry.py` exposing `register_trainer(name, fn)` and `register_task_type(name, schema)`. Document a contributed-plugin example (e.g. a Timm-based trainer). Used by training service to look up the trainer.
3. **API pagination + search** (filters on all list endpoints, server-side ordering, full-text search where pgvector/`pg_trgm` makes sense).
4. **Better active-learning uncertainty**
   - When a `ModelArtifact` exists for the project, score AL candidates by real per-asset entropy / margin instead of the random bootstrap. Random remains the default for cold-start projects.
5. **Annotation history diff UI**
   - Render the JSON diff between annotation versions (we already store `history`).

**Exit criteria:** a user can stand up an inference cluster, point projects at it, and serve predictions independently of the API container. Plugin authors can ship a new trainer without touching core code.

---

## Phase 5 — Production Hardening

Focus: things that block a real prod deployment.

1. **MFA + SSO** (deferred from the original plan)
   - OIDC (Google) and SAML (Okta). Auth architecture stays provider-agnostic.
2. **Kubernetes / Helm chart**
   - Replace docker-compose for prod. Per-cluster agent install moves to a Helm sub-chart; ConfigMap-driven cluster registration.
3. **CI/CD via GitHub Actions**
   - PR pipeline: lint → unit → integration (services in containers) → contract → Playwright visual.
   - Release pipeline: build & sign images, push to GHCR, Helm chart release.
4. **Production frontend build**
   - Replace Vite dev server in `docker-compose` with an nginx stage serving the `vite build` output.
5. **Hardening pass**
   - Parameterise CORS origins per env (already partly done — verify).
   - Access-token refresh logic in `auth-store.tsx`.
   - Secrets via Vault / K8s secrets, not env files.
   - Pen-test pass on auth + upload paths; OWASP top-10 review.
6. **Operations**
   - Backup / restore runbooks for Postgres + MinIO.
   - Grafana alert rules (error rate, queue depth, cluster heartbeat staleness).
   - One-command agent install script: `curl ... | bash` → `docker run` with token.

**Exit criteria:** a customer can deploy VisionForge into their own cloud account from a Helm chart, with CI gates, automated backups, alerting, SSO, and a documented agent install path.

---

## Quick wins to sequence first

If we want a tight first PR after this audit, these are the cheapest wins from Phase 2 + Phase 3:

1. ONNX export cluster picker (frontend-only; backend already supports it).
2. Pre-populate annotator classes from `ClassMap` (one fetch + state seed).
3. `/api/artifacts/models/{id}/download` endpoint + DOWNLOAD button.
4. System status panel wired to `/health`.

Each is < ~50 lines and ships a visible improvement.
