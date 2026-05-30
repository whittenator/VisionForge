# Training UX Overhaul — Spec

## Problem

The training flow is functional but not seamless or fully controllable:

- **Splits are inconsistent and invisible.** Training hardcoded a round-robin
  80/20 split and never held out a test set, while evaluation reads
  `asset.meta_data.split` — so the two disagreed and nothing was persisted to
  visualize.
- **Only a subset of Ultralytics hyperparameters/augmentations** were reachable
  from the UI/backend.
- **Completed-run metrics barely rendered** (the chart looked for clean keys that
  Ultralytics never emits) and the native plots (PR curve, confusion matrix,
  results grid) were discarded.
- **Test-set evaluation was not discoverable** from a finished run.

## Goals

1. Configurable, persisted, reproducible train/val/test splits honored by both
   training and evaluation, with visualization and per-split browsing.
2. Full coverage of Ultralytics training hyperparameters and online
   augmentations in the launch form and backend.
3. Gold-standard CV metric visualization for completed runs: train/val loss
   curves, mAP50 / mAP50-95, precision/recall, LR schedule, summary tiles, and
   the native Ultralytics plot images.
4. One-click "Run Evaluation" on the test split from a completed run, plus a list
   of that model's evaluations.

## Non-goals

- Live augmentation image preview.
- Hyperparameter sweeps / multi-run comparison.

## Design

- **Splits** persist into the existing `asset.meta_data` JSON (`split` key, the
  same field evaluation already reads). `split_service` assigns them
  deterministically (seeded, optionally class-stratified) and summarizes them.
  Training honors persisted splits and falls back to a deterministic hash split;
  **test assets are held out** of the YOLO dataset.
- **Hyperparameters/augmentations** flow through an allow-list
  (`ULTRALYTICS_TRAIN_ARGS`) applied with `plots=True`. The UI is config-driven
  (single field-metadata array) and grouped (Core / Optimizer & Schedule /
  Regularization & Loss / Augmentation).
- **Metrics** are normalized to clean keys at capture time and stored in
  `experiment_runs.metrics_json` alongside a `summary`, the `split`, and `plots`
  (uploaded to MinIO and surfaced with presigned URLs).
- **Evaluation** is launched from the run detail page via the existing
  `/evaluations/new` query-param prefill.

No schema migration is required — only existing JSON/Text columns are used.

## API surface

- `GET/POST /api/datasets/{dataset_id}/versions/{version_id}/split`
- `GET /api/datasets/{dataset_id}/assets?split=train|val|test`
- `GET /api/experiments/runs/{runId}/metrics` → `{metrics, summary, plots, split}`
- `GET /api/experiments/runs/{runId}/plots/{name}` (streaming fallback)
- `GET /api/experiments/runs/{runId}` now includes `artifacts`

## Acceptance

- Splits set in the form are persisted, visualized, and are exactly what training
  trains on; test split is unseen during training.
- All documented Ultralytics knobs are settable and forwarded.
- Run detail shows populated loss/mAP/PR/LR charts, summary tiles, and native
  plots; "Run Evaluation" lands on a prefilled eval form.
