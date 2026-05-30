# Training UX Overhaul — Tasks

- [x] `split_service` with deterministic seeded + stratified assignment
- [x] `SplitConfig` / `SplitSummary` schemas
- [x] Split GET/POST endpoints + `?split=` asset filter (+ download_url)
- [x] `storage.put_bytes` / `get_bytes`
- [x] Training honors persisted split, holds out test, hash fallback
- [x] `ULTRALYTICS_TRAIN_ARGS` full hyperparameter/aug passthrough (`plots=True`)
- [x] Metric key normalization + `{summary, plots, split}` in metrics_json
- [x] Plot upload to MinIO + `/metrics` (presigned) and `/plots/{name}` stream
- [x] Run detail exposes `artifacts`
- [x] `SplitPanel` component
- [x] Config-driven grouped training form + embedded split
- [x] Multi-panel run-detail charts, summary tiles, plot gallery, Run Evaluation
- [x] Split service unit tests
- [ ] Playwright visual snapshots (run when UI review needed)
