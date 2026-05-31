# Timm Image Classification + Pluggable Training Backends — Plan

## Backend

### New package `app/services/training/`
- `base.py` — `Trainer` ABC, `TrainContext`, `TrainResult`, `FieldDef`,
  `FieldGroup`, `Capabilities`.
- `registry.py` — `register`, `get_trainer` (default `ultralytics`),
  `list_frameworks`, `UnknownFrameworkError`, `DEFAULT_FRAMEWORK`.
- `datasets.py` — `build_imagefolder`, `build_yolo_detect`, `extract_minio_key`,
  `fetch_image_bytes` (extracted from the old `_build_yolo_dataset`).
- `ultralytics_trainer.py` — `UltralyticsTrainer` (detect/classify/segment/pose);
  carries `ULTRALYTICS_TRAIN_ARGS`, `_METRIC_KEY_MAP`, `_PLOT_FILES`, the YOLO
  train callback, `export_onnx`, and the YOLO predict helpers.
- `timm_trainer.py` — `TimmTrainer` (classify): full training loop
  (`create_model` / `create_transform` / `create_optimizer_v2` /
  `create_scheduler_v2` / `Mixup` / EMA / AMP), self-describing checkpoint,
  matplotlib plots, `export_onnx` via `torch.onnx.export`, `load_predictor` +
  `predict_classification`. All ML imports lazy.

### Orchestration (thin dispatch — no library names)
- `jobs/tasks/training.py` — keeps scaffolding (load run, resolve
  assets/annotations/classmap, split resolution, MinIO, metrics blob, artifact +
  plot upload, job status); resolves `framework` → `get_trainer` → `trainer.run`.
- `jobs/tasks/onnx_export.py` — dispatches to `get_trainer(framework).export_onnx`.
- `jobs/tasks/evaluation.py` — `_load_model` / `_predict_*` dispatch via registry.
- `services/inference_service.py` — `_load_artifact` / `predict` dispatch via
  registry + `artifact.framework`.

### Models / schema / API / deps
- `models/experiment.py`, `models/artifact.py` — add nullable `framework`.
- `db/migrations/versions/0008_training_framework.py` — merge the two heads
  (`0004_cluster_discovery`, `0007_phase2_task_type_and_review`) + add columns.
- `schemas/common.py` — `TrainRequest.framework`.
- `services/training_service.py` — `framework` param, task validation, persist.
- `api/training.py` — capabilities + model-search endpoints; mounted in `main.py`.
- `requirements.txt` — add `timm>=1.0`, `matplotlib>=3.8` (propagate to agents).

## Frontend
- `pages/experiments/new.tsx` — schema-driven; Framework selector; task/model/
  hyperparameter sections from capabilities; searchable Timm backbone picker;
  `framework` added to the `/api/train` body.

## Tests
- `tests/unit/test_training_registry.py`, `test_training_datasets.py`,
  `test_training_frameworks_api.py`, `test_timm_trainer.py` (schema + gated CPU
  smoke), and extensions to `test_services_training.py`.
