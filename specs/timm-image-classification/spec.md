# Timm Image Classification + Pluggable Training Backends — Spec

## Problem

VisionForge could only train **Ultralytics/YOLO** models. The trainer was
hard-wired into the Celery task (direct `from ultralytics import YOLO`), and the
same coupling existed in ONNX export, evaluation, and inference. The frontend
hard-coded the YOLO model list and the entire hyperparameter form. There was no
way to:

- Train image classifiers with **Timm** (PyTorch Image Models) — the de-facto
  library for classification backbones.
- Mix-and-match Timm architecture pieces (any of ~1300 backbones, pooling heads,
  drop rates, pretrained) with full control over hyperparameters and
  augmentations.
- Add any *other* training library later without editing the orchestration code.

## Goals

1. A **pluggable training-backend abstraction**: each library is a `Trainer`
   plugin registered in a registry; the Celery task, export, evaluation, and
   inference resolve a trainer by key and delegate. No library names hard-coded
   in orchestration code.
2. A **Timm** trainer for image classification exposing the *full* surface:
   every backbone (searchable), head/pooling + drop rates, the complete
   optimizer/scheduler matrix, mixup/cutmix, model EMA, label smoothing, AMP,
   channels-last, and the full augmentation pipeline.
3. A **backend-driven capabilities API** so the frontend renders each
   framework's training form dynamically — selecting Timm vs Ultralytics is
   seamless and requires no framework-specific UI code.
4. Full **model lifecycle** for Timm classifiers: training, ONNX export, and
   evaluation/inference.
5. Ultralytics behavior is **unchanged** (pure extraction behind the interface).

## Non-goals

- Timm tasks other than classification (detection/segmentation stay YOLO).
- Hyperparameter sweeps / multi-run comparison.
- Distributed/multi-GPU training loops (single-process loop; cluster routing
  reuses the existing per-cluster queue mechanism).

## Design

### Abstraction (`backend/src/app/services/training/`)

- `base.py` — `Trainer` ABC + `TrainContext` (the shared surface: db, run,
  params, task, class_names, assets, annotations, splits, MinIO, work_dir, and a
  uniform `report(progress, epoch)` callback), `TrainResult`, and serializable
  `FieldDef`/`FieldGroup`/`Capabilities` describing the form.
- `registry.py` — `register` / `get_trainer` (defaults to `ultralytics` for
  back-compat) / `list_frameworks`.
- `datasets.py` — shared exporters: `build_imagefolder` (classification,
  reused by both Ultralytics-classify and Timm) and `build_yolo_detect`.
- `ultralytics_trainer.py` — behavior-preserving extraction of the YOLO logic.
- `timm_trainer.py` — the Timm classification training loop + export + predict.

### Framework persistence

A nullable `framework` column on `experiment_runs` and `model_artifacts`
(migration `0008`, which also merges the two pre-existing migration heads).
`framework` is also stored in `params_json` and each `run.artifacts[]` entry.
The Timm checkpoint is a **self-describing dict** (`vf_framework`, `arch`,
`global_pool`, `img_size`, `classes`, `state_dict`) so export/inference rebuild
the model from the artifact alone.

### API

- `GET /api/training/frameworks` → every framework's capability descriptor.
- `GET /api/training/frameworks/{key}/models?task=&query=` → searchable model
  catalogue (Timm's full list via `timm.list_models`).
- `POST /api/train` gains an optional `framework` field (default `ultralytics`);
  `launch_training` validates the task against the trainer's `supported_tasks`.

### Frontend

`pages/experiments/new.tsx` is schema-driven: it fetches the frameworks, renders
a Framework selector, derives Task options + model catalogue + hyperparameter
sections from the chosen framework's capabilities, and adds a searchable backbone
picker for Timm. The existing FieldDef/HpField/Section machinery is reused, now
fed from the API.

## Acceptance criteria

- Selecting **Timm** in the launch form shows classification-only tasks, a
  searchable backbone picker, and Timm's hyperparameter/augmentation groups;
  selecting **Ultralytics** reproduces today's form exactly.
- A Timm run trains on CPU/GPU, reports per-epoch `top1`/`top5`, stores a
  `pytorch` artifact tagged `framework=timm`, and uploads loss/confusion plots.
- ONNX export and evaluation work on a Timm-trained classifier.
- Existing YOLO detection runs behave identically.
- `alembic upgrade head` resolves to a single head and adds the columns.
- Adding a new library requires only a new `Trainer` module + `register(...)`.
