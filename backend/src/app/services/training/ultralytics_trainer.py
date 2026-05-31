"""Ultralytics/YOLO training backend.

This is a behaviour-preserving extraction of the YOLO logic that previously
lived inline in ``jobs/tasks/training.py`` (training), ``jobs/tasks/onnx_export``
(export) and the inference/evaluation predict helpers. It now implements the
:class:`Trainer` interface so it sits behind the same abstraction as Timm.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.training import datasets
from app.services.training.base import (
    Capabilities,
    FieldDef,
    FieldGroup,
    TrainContext,
    Trainer,
    TrainResult,
)
from app.services.training.registry import register

# Map Ultralytics' verbose metric keys to the clean keys the frontend charts.
_METRIC_KEY_MAP = {
    "metrics/mAP50(B)": "mAP50",
    "metrics/mAP50-95(B)": "mAP50_95",
    "metrics/precision(B)": "precision",
    "metrics/recall(B)": "recall",
    "train/box_loss": "train_box_loss",
    "train/cls_loss": "train_cls_loss",
    "train/dfl_loss": "train_dfl_loss",
    "val/box_loss": "val_box_loss",
    "val/cls_loss": "val_cls_loss",
    "val/dfl_loss": "val_dfl_loss",
    "lr/pg0": "lr",
    "metrics/accuracy_top1": "top1",
    "metrics/accuracy_top5": "top5",
}

# Allow-list of ``model.train()`` args users may tune. Keys absent here are
# ignored so callers cannot inject unsafe/irrelevant kwargs.
ULTRALYTICS_TRAIN_ARGS: dict[str, Any] = {
    "epochs": 50,
    "imgsz": 640,
    "batch": 16,
    "patience": 100,
    "rect": False,
    "single_cls": False,
    "seed": 0,
    "optimizer": "auto",
    "lr0": 0.01,
    "lrf": 0.01,
    "momentum": 0.937,
    "weight_decay": 0.0005,
    "warmup_epochs": 3.0,
    "warmup_momentum": 0.8,
    "warmup_bias_lr": 0.1,
    "cos_lr": False,
    "close_mosaic": 10,
    "nbs": 64,
    "amp": True,
    "dropout": 0.0,
    "label_smoothing": 0.0,
    "box": 7.5,
    "cls": 0.5,
    "dfl": 1.5,
    "overlap_mask": True,
    "mask_ratio": 4,
    "freeze": None,
    "hsv_h": 0.015,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "degrees": 0.0,
    "translate": 0.1,
    "scale": 0.5,
    "shear": 0.0,
    "perspective": 0.0,
    "flipud": 0.0,
    "fliplr": 0.5,
    "bgr": 0.0,
    "mosaic": 1.0,
    "mixup": 0.0,
    "copy_paste": 0.0,
    "erasing": 0.4,
    "crop_fraction": 1.0,
    "auto_augment": "randaugment",
}

# Plot images Ultralytics writes into the run dir when plots=True.
_PLOT_FILES = [
    "results.png",
    "PR_curve.png",
    "P_curve.png",
    "R_curve.png",
    "F1_curve.png",
    "confusion_matrix.png",
    "confusion_matrix_normalized.png",
    "labels.jpg",
    "BoxPR_curve.png",
]

_SIZES = ["n", "s", "m", "l", "x"]


def _normalize_metrics(raw: dict) -> dict:
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k in _METRIC_KEY_MAP:
            out[_METRIC_KEY_MAP[k]] = v
        out[k] = v
    return out


class UltralyticsTrainer(Trainer):
    key = "ultralytics"
    label = "Ultralytics (YOLO)"
    supported_tasks = {"detect", "classify", "segment", "pose"}

    def capabilities(self) -> Capabilities:
        models_by_task = {
            "detect": [f"yolov8{s}.pt" for s in _SIZES],
            "classify": [f"yolov8{s}-cls.pt" for s in _SIZES],
            "segment": [f"yolov8{s}-seg.pt" for s in _SIZES],
            "pose": [f"yolov8{s}-pose.pt" for s in _SIZES],
        }
        groups = [
            FieldGroup(
                "Core",
                [
                    FieldDef("epochs", "Epochs", "number", 50, 1, 2000),
                    FieldDef("batch", "Batch Size", "number", 16, 1, 512),
                    FieldDef("imgsz", "Image Size", "number", 640, 32, 1920, 32),
                    FieldDef(
                        "patience",
                        "Patience",
                        "number",
                        100,
                        0,
                        1000,
                        help="Early-stop after N epochs w/o improvement",
                    ),
                    FieldDef("seed", "Seed", "number", 0, 0),
                    FieldDef(
                        "rect",
                        "Rectangular",
                        "bool",
                        False,
                        help="Rectangular batches (min padding)",
                    ),
                    FieldDef("single_cls", "Single class", "bool", False),
                ],
            ),
            FieldGroup(
                "Optimizer & Schedule",
                [
                    FieldDef(
                        "optimizer",
                        "Optimizer",
                        "select",
                        "auto",
                        options=["auto", "SGD", "Adam", "AdamW", "NAdam", "RAdam", "RMSProp"],
                    ),
                    FieldDef("lr0", "Initial LR (lr0)", "number", 0.01, 0.00001, 1, 0.0001),
                    FieldDef("lrf", "Final LR (lrf)", "number", 0.01, 0.00001, 1, 0.0001),
                    FieldDef("momentum", "Momentum", "number", 0.937, 0, 1, 0.001),
                    FieldDef("weight_decay", "Weight Decay", "number", 0.0005, 0, 0.1, 0.0001),
                    FieldDef("warmup_epochs", "Warmup Epochs", "number", 3.0, 0, 20, 0.5),
                    FieldDef("warmup_momentum", "Warmup Momentum", "number", 0.8, 0, 1, 0.01),
                    FieldDef("warmup_bias_lr", "Warmup Bias LR", "number", 0.1, 0, 1, 0.01),
                    FieldDef("cos_lr", "Cosine LR", "bool", False),
                    FieldDef(
                        "close_mosaic",
                        "Close Mosaic",
                        "number",
                        10,
                        0,
                        100,
                        help="Disable mosaic for last N epochs",
                    ),
                    FieldDef("nbs", "Nominal Batch", "number", 64, 1, 256),
                    FieldDef("amp", "AMP", "bool", True, help="Automatic mixed precision"),
                ],
            ),
            FieldGroup(
                "Regularization & Loss Gains",
                [
                    FieldDef("dropout", "Dropout", "number", 0.0, 0, 1, 0.01),
                    FieldDef("label_smoothing", "Label Smoothing", "number", 0.0, 0, 1, 0.01),
                    FieldDef("box", "Box Gain", "number", 7.5, 0, 20, 0.1),
                    FieldDef("cls", "Cls Gain", "number", 0.5, 0, 10, 0.1),
                    FieldDef("dfl", "DFL Gain", "number", 1.5, 0, 10, 0.1),
                    FieldDef("overlap_mask", "Overlap Mask", "bool", True),
                    FieldDef("mask_ratio", "Mask Ratio", "number", 4, 1, 16),
                ],
            ),
            FieldGroup(
                "Augmentation",
                [
                    FieldDef("hsv_h", "hsv_h", "number", 0.015, 0, 1, 0.001, help="Hue jitter"),
                    FieldDef("hsv_s", "hsv_s", "number", 0.7, 0, 1, 0.01, help="Saturation jitter"),
                    FieldDef("hsv_v", "hsv_v", "number", 0.4, 0, 1, 0.01, help="Value jitter"),
                    FieldDef("degrees", "degrees", "number", 0.0, 0, 180, 1, help="Rotation range"),
                    FieldDef("translate", "translate", "number", 0.1, 0, 1, 0.01),
                    FieldDef("scale", "scale", "number", 0.5, 0, 1, 0.01),
                    FieldDef("shear", "shear", "number", 0.0, 0, 10, 0.1),
                    FieldDef("perspective", "perspective", "number", 0.0, 0, 0.001, 0.0001),
                    FieldDef("flipud", "flipud", "number", 0.0, 0, 1, 0.01),
                    FieldDef("fliplr", "fliplr", "number", 0.5, 0, 1, 0.01),
                    FieldDef("bgr", "bgr", "number", 0.0, 0, 1, 0.01),
                    FieldDef("mosaic", "mosaic", "number", 1.0, 0, 1, 0.01),
                    FieldDef("mixup", "mixup", "number", 0.0, 0, 1, 0.01),
                    FieldDef("copy_paste", "copy_paste", "number", 0.0, 0, 1, 0.01),
                    FieldDef("erasing", "erasing", "number", 0.4, 0, 1, 0.01),
                    FieldDef("crop_fraction", "crop_fraction", "number", 1.0, 0, 1, 0.01),
                    FieldDef(
                        "auto_augment",
                        "auto_augment",
                        "select",
                        "randaugment",
                        options=["randaugment", "autoaugment", "augmix"],
                    ),
                ],
            ),
        ]
        return Capabilities(
            key=self.key,
            label=self.label,
            supported_tasks=sorted(self.supported_tasks),
            models_by_task=models_by_task,
            groups=groups,
            device_options=["cpu", "cuda", "mps", "0", "0,1"],
        )

    def run(self, ctx: TrainContext) -> TrainResult:
        from ultralytics import YOLO  # type: ignore

        params = ctx.params
        base_model = params.get("base_model", "yolov8n.pt")
        dataset_dir = ctx.work_dir / "dataset"

        if ctx.task == "classify":
            data_arg = datasets.build_imagefolder(
                ctx.assets,
                ctx.annotations_by_asset,
                ctx.class_names,
                dataset_dir,
                ctx.minio_client,
                ctx.bucket,
                ctx.splits,
            )
        else:
            data_arg = datasets.build_yolo_detect(
                ctx.assets,
                ctx.annotations_by_asset,
                ctx.class_names,
                dataset_dir,
                ctx.minio_client,
                ctx.bucket,
                ctx.splits,
            )

        ctx.report(progress=0.2)

        output_dir = ctx.work_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        total_epochs = params.get("epochs", 50)
        model = YOLO(base_model)

        def on_train_epoch_end(trainer: Any) -> None:  # noqa: ANN001
            epoch_num = getattr(trainer, "epoch", 0)
            metrics_dict: dict = {}
            if hasattr(trainer, "metrics"):
                raw_metrics = trainer.metrics
                if hasattr(raw_metrics, "results_dict"):
                    metrics_dict = dict(raw_metrics.results_dict)
                elif isinstance(raw_metrics, dict):
                    metrics_dict = raw_metrics
            if hasattr(trainer, "loss"):
                loss_val = trainer.loss
                metrics_dict["loss"] = float(loss_val) if loss_val is not None else None
            entry = {"epoch": epoch_num, **_normalize_metrics(metrics_dict)}
            progress = 0.2 + 0.75 * (epoch_num / max(total_epochs, 1))
            ctx.report(progress=progress, epoch=entry)

        model.add_callback("on_train_epoch_end", on_train_epoch_end)

        train_kwargs: dict = {
            "data": str(data_arg),
            "device": params.get("device", "cpu"),
            "project": str(output_dir),
            "name": "train",
            "plots": True,
        }
        for key, default in ULTRALYTICS_TRAIN_ARGS.items():
            val = params.get(key, default)
            if val is not None:
                train_kwargs[key] = val
        train_kwargs["epochs"] = total_epochs
        model.train(**train_kwargs)

        best = output_dir / "train" / "weights" / "best.pt"
        if not best.exists():
            pts = list(output_dir.rglob("*.pt"))
            best = pts[0] if pts else None

        results_dir = output_dir / "train"
        plot_files = [results_dir / f for f in _PLOT_FILES if (results_dir / f).exists()]

        return TrainResult(best_model_path=best, plot_files=plot_files)

    # -- export / inference ---------------------------------------------------
    def export_onnx(
        self, local_pt: Path, out_dir: Path, *, opset: int | None = None, dynamic: bool = True
    ) -> Path | None:
        from ultralytics import YOLO  # type: ignore

        model = YOLO(str(local_pt))
        export_kwargs: dict = {"format": "onnx", "simplify": True, "dynamic": bool(dynamic)}
        if opset is not None:
            export_kwargs["opset"] = int(opset)
        result = model.export(**export_kwargs)
        if result:
            return Path(str(result))
        candidate = local_pt.with_suffix(".onnx")
        return candidate if candidate.exists() else None

    def load_predictor(self, local_pt: Path) -> Any:
        from ultralytics import YOLO  # type: ignore

        return YOLO(str(local_pt))

    def predict_classification(self, predictor: Any, image_path: str) -> tuple[str, float]:
        results = predictor.predict(image_path, verbose=False)
        for r in results:
            probs = getattr(r, "probs", None)
            if probs is not None:
                top = int(probs.top1)
                names = getattr(r, "names", {}) or {}
                return (names.get(top, str(top)), float(probs.top1conf.item()))
        return ("unknown", 0.0)

    def predict_detections(
        self, predictor: Any, image_path: str, score_threshold: float
    ) -> list[dict[str, Any]]:
        results = predictor.predict(image_path, conf=score_threshold, verbose=False)
        out: list[dict[str, Any]] = []
        for r in results:
            names = getattr(r, "names", {}) or {}
            for box in getattr(r, "boxes", []) or []:
                cls_idx = int(box.cls.item()) if hasattr(box, "cls") else 0
                xy = box.xywh[0].tolist() if hasattr(box, "xywh") else [0, 0, 0, 0]
                cx, cy, w, h = xy
                out.append(
                    {
                        "class": names.get(cls_idx, str(cls_idx)),
                        "bbox": (cx - w / 2, cy - h / 2, w, h),
                        "score": float(box.conf.item()) if hasattr(box, "conf") else 0.0,
                    }
                )
        return out


register(UltralyticsTrainer())
