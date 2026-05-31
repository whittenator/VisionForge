# Timm Image Classification + Pluggable Training Backends — Tasks

## Abstraction layer
- [x] `services/training/base.py` — Trainer ABC, TrainContext, TrainResult, schema dataclasses
- [x] `services/training/registry.py` — register / get_trainer / list_frameworks
- [x] `services/training/datasets.py` — shared ImageFolder + YOLO-detect exporters

## Trainers
- [x] `services/training/ultralytics_trainer.py` — behavior-preserving YOLO extraction
- [x] `services/training/timm_trainer.py` — full Timm classification loop + export + predict

## Orchestration (generalized dispatch)
- [x] Thin `jobs/tasks/training.py` delegating to the resolved trainer
- [x] `jobs/tasks/onnx_export.py` dispatches export by framework
- [x] `jobs/tasks/evaluation.py` loader/predict dispatch via registry
- [x] `services/inference_service.py` loader/predict dispatch via registry

## Persistence / API / deps
- [x] `framework` column on ExperimentRun + ModelArtifact
- [x] Alembic `0008` merges the two heads + adds columns
- [x] `TrainRequest.framework`; `launch_training` validates + persists framework
- [x] `api/training.py` capabilities + model-search endpoints; registered in main
- [x] `requirements.txt` — `timm`, `matplotlib`

## Frontend
- [x] Schema-driven `experiments/new.tsx` (framework selector, searchable backbone, dynamic groups)

## Tests
- [x] Registry, datasets, capabilities API, framework persistence, Timm schema
- [x] Gated CPU smoke train for Timm (`importorskip`)

## Verification
- [x] `pytest backend/tests/unit/` green (125 passed, 1 skipped)
- [x] ruff + black clean on changed files
- [x] `tsc --noEmit` clean for `experiments/new.tsx`
- [x] `alembic heads` → single head; merge verified
- [ ] End-to-end docker-compose smoke (train → export → evaluate a Timm run)
