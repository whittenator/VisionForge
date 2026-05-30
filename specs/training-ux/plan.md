# Training UX Overhaul — Plan

## Backend

1. **`services/split_service.py`** (new) — deterministic, seeded, optionally
   class-stratified split assignment persisted into `asset.meta_data.split`;
   `asset_split`, `normalize_ratios`, `resolve_split` (hash fallback),
   `assign_splits`, `get_split_summary`.
2. **`schemas/split.py`** (new) — `SplitConfig`, `SplitSummary`.
3. **`services/asset_service.py`** — `list_assets` gains a `split` filter
   (filtered in Python since the value lives in JSON).
4. **`api/assets.py`** — `GET/POST /datasets/{id}/versions/{vid}/split`; asset
   list returns `split` + `download_url` and accepts `?split=`.
5. **`services/storage.py`** — `put_bytes` / `get_bytes` helpers.
6. **`jobs/tasks/training.py`** —
   - honor persisted split with deterministic hash fallback; **hold out test**;
   - `ULTRALYTICS_TRAIN_ARGS` allow-list applied with `plots=True`;
   - `_normalize_metrics` maps Ultralytics keys → clean keys;
   - persist `{epochs, split, summary, plots}` in `metrics_json`; upload plot
     PNGs to MinIO.
7. **`api/experiments.py`** / **`schemas/experiment.py`** — `/metrics` returns
   `summary`/`plots`/`split` (+ presigned plot urls); new `/plots/{name}`
   stream; run detail exposes `artifacts`.

## Frontend

8. **`components/common/SplitPanel.tsx`** (new) — ratio/seed/stratify controls,
   stacked split bar, per-class table; persists via the split endpoint.
9. **`pages/experiments/new.tsx`** — config-driven grouped HP/aug form
   (Core / Optimizer & Schedule / Regularization & Loss / Augmentation),
   embedded SplitPanel, device select; persists split on launch.
10. **`pages/experiments/[runId].tsx`** — multi-panel charts (loss / mAP / P-R /
    accuracy / LR), summary tiles, split bar, native plot gallery w/ lightbox,
    "Run Evaluation" + evaluations list.

## Tests
- `tests/unit/test_split_service.py` — ratios, determinism, slice-sum,
  persistence, reproducibility, meta-data reads.

No DB migration (reuses existing JSON/Text columns).
