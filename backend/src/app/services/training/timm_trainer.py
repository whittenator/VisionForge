"""Timm (PyTorch Image Models) training backend for image classification.

Gives users the full Timm surface: any of the ~1300 backbones, head/pooling
choices (``global_pool``, drop rates), the complete optimizer/scheduler matrix
(``create_optimizer_v2`` / ``create_scheduler_v2``), mixup/cutmix, model EMA,
label smoothing, AMP, channels-last, and the full timm augmentation pipeline
(RandAugment/AutoAugment via the ``aa`` string, color jitter, random erasing,
flips, random-resized-crop scale/ratio, interpolation, crop pct).

All torch/timm imports are lazy so this module loads in environments without
the ML wheels (the capability schema is pure data). When the wheels are absent
at run time, :meth:`run` raises and the task records a clean failure — mirroring
the existing Ultralytics ``ImportError`` handling.
"""

from __future__ import annotations

import copy
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

# A small, popular default set surfaced before the user searches the full
# catalogue (the frontend uses the searchable picker against list_models).
_POPULAR = [
    "resnet18",
    "resnet50",
    "resnext50_32x4d",
    "efficientnet_b0",
    "efficientnet_b3",
    "convnext_tiny",
    "convnext_small",
    "mobilenetv3_large_100",
    "mobilenetv3_small_050",
    "vit_tiny_patch16_224",
    "vit_small_patch16_224",
    "vit_base_patch16_224",
    "swin_tiny_patch4_window7_224",
    "deit3_small_patch16_224",
    "resnet10t",
]


class TimmTrainer(Trainer):
    key = "timm"
    label = "Timm (PyTorch Image Models)"
    supported_tasks = {"classify"}

    # ------------------------------------------------------------------ schema
    def capabilities(self) -> Capabilities:
        groups = [
            FieldGroup(
                "Architecture",
                [
                    FieldDef(
                        "model",
                        "Backbone",
                        "model",
                        "resnet50",
                        help="Any timm architecture — type to search the full catalogue",
                    ),
                    FieldDef(
                        "pretrained",
                        "Pretrained weights",
                        "bool",
                        True,
                        help="Initialise from ImageNet-pretrained weights",
                    ),
                    FieldDef(
                        "global_pool",
                        "Pooling head",
                        "select",
                        "avg",
                        options=["avg", "max", "avgmax", "catavgmax", ""],
                        help="Classifier global pooling",
                    ),
                    FieldDef("drop_rate", "Dropout", "number", 0.0, 0, 1, 0.01),
                    FieldDef(
                        "drop_path_rate",
                        "Drop path (stochastic depth)",
                        "number",
                        0.0,
                        0,
                        1,
                        0.01,
                    ),
                ],
            ),
            FieldGroup(
                "Core",
                [
                    FieldDef("epochs", "Epochs", "number", 20, 1, 2000),
                    FieldDef("batch_size", "Batch Size", "number", 32, 1, 1024),
                    FieldDef("img_size", "Image Size", "number", 224, 32, 1024, 16),
                    FieldDef("num_workers", "Data Workers", "number", 4, 0, 32),
                    FieldDef("seed", "Seed", "number", 42, 0),
                    FieldDef(
                        "patience",
                        "Early-stop Patience",
                        "number",
                        0,
                        0,
                        1000,
                        help="Stop after N epochs w/o top-1 improvement (0 = off)",
                    ),
                    FieldDef("amp", "AMP", "bool", True, help="Automatic mixed precision"),
                    FieldDef("channels_last", "Channels-last", "bool", False),
                ],
            ),
            FieldGroup(
                "Optimizer",
                [
                    FieldDef(
                        "opt",
                        "Optimizer",
                        "select",
                        "adamw",
                        options=[
                            "sgd",
                            "momentum",
                            "adam",
                            "adamw",
                            "nadam",
                            "radam",
                            "rmsprop",
                            "lamb",
                            "adabelief",
                        ],
                    ),
                    FieldDef("lr", "Learning Rate", "number", 0.001, 0.0, 10, 0.0001),
                    FieldDef("weight_decay", "Weight Decay", "number", 0.0001, 0, 1, 0.0001),
                    FieldDef("momentum", "Momentum (SGD)", "number", 0.9, 0, 1, 0.001),
                    FieldDef("opt_eps", "Epsilon", "number", 1e-8, 0, 1, 1e-9),
                    FieldDef(
                        "layer_decay",
                        "Layer-wise LR decay",
                        "number",
                        0.0,
                        0,
                        1,
                        0.01,
                        help="0 disables; e.g. 0.75 for ViT fine-tuning",
                    ),
                ],
            ),
            FieldGroup(
                "Schedule",
                [
                    FieldDef(
                        "sched",
                        "Scheduler",
                        "select",
                        "cosine",
                        options=["cosine", "step", "multistep", "plateau", "poly", "tanh", "none"],
                    ),
                    FieldDef("warmup_epochs", "Warmup Epochs", "number", 3, 0, 100),
                    FieldDef("warmup_lr", "Warmup LR", "number", 1e-5, 0, 1, 1e-6),
                    FieldDef("min_lr", "Min LR", "number", 1e-6, 0, 1, 1e-7),
                    FieldDef("decay_epochs", "Decay Epochs (step)", "number", 30, 1, 1000),
                    FieldDef("decay_rate", "Decay Rate", "number", 0.1, 0, 1, 0.01),
                    FieldDef("cooldown_epochs", "Cooldown Epochs", "number", 0, 0, 100),
                ],
            ),
            FieldGroup(
                "Regularization",
                [
                    FieldDef("smoothing", "Label Smoothing", "number", 0.1, 0, 1, 0.01),
                    FieldDef("mixup", "Mixup alpha", "number", 0.0, 0, 5, 0.1),
                    FieldDef("cutmix", "CutMix alpha", "number", 0.0, 0, 5, 0.1),
                    FieldDef("mixup_prob", "Mix prob", "number", 1.0, 0, 1, 0.05),
                    FieldDef("mixup_switch_prob", "Mix switch prob", "number", 0.5, 0, 1, 0.05),
                    FieldDef("model_ema", "Model EMA", "bool", False),
                    FieldDef("model_ema_decay", "EMA decay", "number", 0.9998, 0.9, 1, 0.0001),
                ],
            ),
            FieldGroup(
                "Augmentation",
                [
                    FieldDef(
                        "aa",
                        "Auto-augment policy",
                        "text",
                        "rand-m9-mstd0.5",
                        help="timm AA string, e.g. rand-m9-mstd0.5 / original / v0 (blank = off)",
                    ),
                    FieldDef("color_jitter", "Color Jitter", "number", 0.4, 0, 1, 0.01),
                    FieldDef("reprob", "Random Erase prob", "number", 0.25, 0, 1, 0.01),
                    FieldDef(
                        "remode",
                        "Random Erase mode",
                        "select",
                        "pixel",
                        options=["const", "rand", "pixel"],
                    ),
                    FieldDef("recount", "Random Erase count", "number", 1, 1, 10),
                    FieldDef("hflip", "Horizontal flip prob", "number", 0.5, 0, 1, 0.01),
                    FieldDef("vflip", "Vertical flip prob", "number", 0.0, 0, 1, 0.01),
                    FieldDef("scale_min", "RRC scale min", "number", 0.08, 0, 1, 0.01),
                    FieldDef("scale_max", "RRC scale max", "number", 1.0, 0, 1, 0.01),
                    FieldDef("ratio_min", "RRC ratio min", "number", 0.75, 0.1, 2, 0.01),
                    FieldDef("ratio_max", "RRC ratio max", "number", 1.3333, 0.5, 4, 0.01),
                    FieldDef(
                        "train_interpolation",
                        "Interpolation",
                        "select",
                        "bicubic",
                        options=["bilinear", "bicubic", "random"],
                    ),
                    FieldDef("crop_pct", "Eval crop pct", "number", 0.875, 0.1, 1, 0.01),
                ],
            ),
        ]
        return Capabilities(
            key=self.key,
            label=self.label,
            supported_tasks=sorted(self.supported_tasks),
            models_by_task={"classify": _POPULAR},
            groups=groups,
            device_options=["cpu", "cuda", "cuda:0", "cuda:1"],
        )

    def list_models(self, task: str, query: str = "") -> list[str]:
        try:
            import timm  # type: ignore
        except Exception:
            return super().list_models(task, query)
        pattern = f"*{query.strip()}*" if query.strip() else ""
        try:
            names = (
                timm.list_models(pattern, pretrained=True)
                if pattern
                else timm.list_models(pretrained=True)
            )
        except Exception:
            return super().list_models(task, query)
        return list(names)[:500]

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _resolve_device(params: dict[str, Any]) -> str:
        import torch  # type: ignore

        requested = str(params.get("device", "")).strip()
        if requested in ("", "auto"):
            return "cuda" if torch.cuda.is_available() else "cpu"
        if requested.startswith("cuda") and not torch.cuda.is_available():
            return "cpu"
        return requested

    def _build_transforms(self, params: dict[str, Any]) -> tuple[Any, Any]:
        from timm.data import create_transform  # type: ignore

        img_size = int(params.get("img_size", 224))
        aa = (params.get("aa") or "").strip() or None
        scale = (float(params.get("scale_min", 0.08)), float(params.get("scale_max", 1.0)))
        ratio = (float(params.get("ratio_min", 0.75)), float(params.get("ratio_max", 1.3333)))
        train_tf = create_transform(
            input_size=img_size,
            is_training=True,
            color_jitter=float(params.get("color_jitter", 0.4)),
            auto_augment=aa,
            interpolation=str(params.get("train_interpolation", "bicubic")),
            re_prob=float(params.get("reprob", 0.25)),
            re_mode=str(params.get("remode", "pixel")),
            re_count=int(params.get("recount", 1)),
            scale=scale,
            ratio=ratio,
            hflip=float(params.get("hflip", 0.5)),
            vflip=float(params.get("vflip", 0.0)),
        )
        val_tf = create_transform(
            input_size=img_size,
            is_training=False,
            interpolation=str(params.get("train_interpolation", "bicubic")),
            crop_pct=float(params.get("crop_pct", 0.875)),
        )
        return train_tf, val_tf

    # -------------------------------------------------------------------- train
    def run(self, ctx: TrainContext) -> TrainResult:  # noqa: C901 - linear training loop
        import timm  # type: ignore
        import torch  # type: ignore
        from torch.utils.data import DataLoader  # type: ignore
        from torchvision.datasets import ImageFolder  # type: ignore

        params = ctx.params
        device = self._resolve_device(params)
        torch.manual_seed(int(params.get("seed", 42)))

        root = datasets.build_imagefolder(
            ctx.assets,
            ctx.annotations_by_asset,
            ctx.class_names,
            ctx.work_dir / "dataset",
            ctx.minio_client,
            ctx.bucket,
            ctx.splits,
        )
        ctx.report(progress=0.2)

        train_tf, val_tf = self._build_transforms(params)
        train_ds = ImageFolder(str(root / "train"), transform=train_tf)
        val_dir = root / "val"
        has_val = val_dir.exists() and any(val_dir.iterdir())
        val_ds = ImageFolder(str(val_dir), transform=val_tf) if has_val else None

        # ImageFolder derives class order from sorted dir names; persist that so
        # predictions map back to the right label.
        classes = train_ds.classes
        num_classes = len(classes)

        batch_size = int(params.get("batch_size", 32))
        num_workers = int(params.get("num_workers", 4))
        train_loader = DataLoader(
            train_ds,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers,
            pin_memory=device.startswith("cuda"),
            drop_last=False,
        )
        val_loader = (
            DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
            if val_ds is not None
            else None
        )

        model = timm.create_model(
            str(params.get("model", "resnet50")),
            pretrained=bool(params.get("pretrained", True)),
            num_classes=num_classes,
            global_pool=str(params.get("global_pool", "avg")),
            drop_rate=float(params.get("drop_rate", 0.0)),
            drop_path_rate=float(params.get("drop_path_rate", 0.0)),
        )
        memory_format = (
            torch.channels_last if params.get("channels_last") else torch.contiguous_format
        )
        model = model.to(device, memory_format=memory_format)

        optimizer = self._make_optimizer(model, params)
        epochs = int(params.get("epochs", 20))
        scheduler, epochs = self._make_scheduler(optimizer, params, epochs)
        mixup_fn = self._make_mixup(params, num_classes)
        train_loss_fn, val_loss_fn = self._make_losses(params, mixup_fn)

        ema = None
        if params.get("model_ema"):
            try:
                from timm.utils import ModelEmaV2  # type: ignore

                ema = ModelEmaV2(model, decay=float(params.get("model_ema_decay", 0.9998)))
            except Exception:
                ema = None

        use_amp = bool(params.get("amp", True)) and device.startswith("cuda")
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

        history: list[dict[str, Any]] = []
        best_top1 = -1.0
        best_state: dict[str, Any] | None = None
        epochs_no_improve = 0
        patience = int(params.get("patience", 0))

        for epoch in range(epochs):
            model.train()
            running_loss, seen = 0.0, 0
            for inputs, targets in train_loader:
                inputs = inputs.to(device, memory_format=memory_format, non_blocking=True)
                targets = targets.to(device, non_blocking=True)
                if mixup_fn is not None and inputs.size(0) % 2 == 0:
                    inputs, targets = mixup_fn(inputs, targets)
                optimizer.zero_grad()
                with torch.cuda.amp.autocast(enabled=use_amp):
                    outputs = model(inputs)
                    loss = train_loss_fn(outputs, targets)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                if ema is not None:
                    ema.update(model)
                running_loss += float(loss.item()) * inputs.size(0)
                seen += inputs.size(0)

            train_loss = running_loss / max(seen, 1)
            eval_model = ema.module if ema is not None else model
            metrics = self._validate(eval_model, val_loader, val_loss_fn, device, memory_format)

            entry = {
                "epoch": epoch,
                "train_loss": round(train_loss, 5),
                "lr": round(optimizer.param_groups[0]["lr"], 8),
                **metrics,
            }
            history.append(entry)
            ctx.report(progress=0.2 + 0.75 * ((epoch + 1) / max(epochs, 1)), epoch=entry)

            top1 = metrics.get("top1", 0.0)
            if top1 > best_top1:
                best_top1 = top1
                best_state = copy.deepcopy(eval_model.state_dict())
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
                if patience and epochs_no_improve >= patience:
                    break

            if scheduler is not None:
                try:
                    scheduler.step(epoch + 1, metric=top1)
                except TypeError:
                    scheduler.step(epoch + 1)

        if best_state is not None:
            model.load_state_dict(best_state)

        img_size = int(params.get("img_size", 224))
        checkpoint = {
            "vf_framework": "timm",
            "arch": str(params.get("model", "resnet50")),
            "num_classes": num_classes,
            "global_pool": str(params.get("global_pool", "avg")),
            "img_size": img_size,
            "classes": classes,
            "state_dict": model.state_dict(),
        }
        best_path = ctx.work_dir / "best.pt"
        torch.save(checkpoint, best_path)

        plot_files = self._make_plots(
            ctx.work_dir, history, model, val_loader, classes, device, memory_format
        )

        final_metrics = {k: v for k, v in history[-1].items() if k != "epoch"} if history else {}
        artifact_meta = {
            "arch": checkpoint["arch"],
            "num_classes": num_classes,
            "global_pool": checkpoint["global_pool"],
            "img_size": img_size,
            "classes": classes,
        }
        return TrainResult(
            best_model_path=best_path,
            final_metrics=final_metrics,
            plot_files=plot_files,
            artifact_meta=artifact_meta,
        )

    # ---------------------------------------------------------- training pieces
    def _make_optimizer(self, model: Any, params: dict[str, Any]) -> Any:
        from timm.optim import create_optimizer_v2  # type: ignore

        kwargs: dict[str, Any] = {
            "opt": str(params.get("opt", "adamw")),
            "lr": float(params.get("lr", 0.001)),
            "weight_decay": float(params.get("weight_decay", 0.0001)),
            "momentum": float(params.get("momentum", 0.9)),
        }
        eps = params.get("opt_eps")
        if eps is not None:
            kwargs["eps"] = float(eps)
        layer_decay = float(params.get("layer_decay", 0.0) or 0.0)
        if layer_decay > 0:
            kwargs["layer_decay"] = layer_decay
        try:
            return create_optimizer_v2(model, **kwargs)
        except TypeError:
            kwargs.pop("eps", None)
            kwargs.pop("layer_decay", None)
            return create_optimizer_v2(model, **kwargs)

    def _make_scheduler(self, optimizer: Any, params: dict[str, Any], epochs: int) -> tuple:
        sched = str(params.get("sched", "cosine"))
        if sched in ("", "none"):
            return None, epochs
        from timm.scheduler import create_scheduler_v2  # type: ignore

        try:
            scheduler, num_epochs = create_scheduler_v2(
                optimizer,
                sched=sched,
                num_epochs=epochs,
                decay_epochs=float(params.get("decay_epochs", 30)),
                decay_rate=float(params.get("decay_rate", 0.1)),
                min_lr=float(params.get("min_lr", 1e-6)),
                warmup_lr=float(params.get("warmup_lr", 1e-5)),
                warmup_epochs=int(params.get("warmup_epochs", 3)),
                cooldown_epochs=int(params.get("cooldown_epochs", 0)),
            )
            return scheduler, int(num_epochs)
        except Exception:
            return None, epochs

    def _make_mixup(self, params: dict[str, Any], num_classes: int) -> Any:
        mixup = float(params.get("mixup", 0.0) or 0.0)
        cutmix = float(params.get("cutmix", 0.0) or 0.0)
        if mixup <= 0 and cutmix <= 0:
            return None
        try:
            from timm.data import Mixup  # type: ignore

            return Mixup(
                mixup_alpha=mixup,
                cutmix_alpha=cutmix,
                prob=float(params.get("mixup_prob", 1.0)),
                switch_prob=float(params.get("mixup_switch_prob", 0.5)),
                mode="batch",
                label_smoothing=float(params.get("smoothing", 0.1)),
                num_classes=num_classes,
            )
        except Exception:
            return None

    def _make_losses(self, params: dict[str, Any], mixup_fn: Any) -> tuple:
        import torch.nn as nn  # type: ignore

        smoothing = float(params.get("smoothing", 0.1))
        if mixup_fn is not None:
            from timm.loss import SoftTargetCrossEntropy  # type: ignore

            train_loss = SoftTargetCrossEntropy()
        elif smoothing > 0:
            try:
                from timm.loss import LabelSmoothingCrossEntropy  # type: ignore

                train_loss = LabelSmoothingCrossEntropy(smoothing=smoothing)
            except Exception:
                train_loss = nn.CrossEntropyLoss(label_smoothing=smoothing)
        else:
            train_loss = nn.CrossEntropyLoss()
        return train_loss, nn.CrossEntropyLoss()

    def _validate(
        self, model: Any, val_loader: Any, loss_fn: Any, device: str, memory_format: Any
    ) -> dict[str, Any]:
        if val_loader is None:
            return {"top1": 0.0, "top5": 0.0, "val_loss": 0.0}
        import torch  # type: ignore

        model.eval()
        total, correct1, correct5, loss_sum = 0, 0, 0, 0.0
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs = inputs.to(device, memory_format=memory_format)
                targets = targets.to(device)
                outputs = model(inputs)
                loss_sum += float(loss_fn(outputs, targets).item()) * inputs.size(0)
                k = min(5, outputs.size(1))
                _, pred = outputs.topk(k, 1, True, True)
                pred = pred.t()
                correct = pred.eq(targets.view(1, -1).expand_as(pred))
                correct1 += int(correct[0].reshape(-1).float().sum().item())
                correct5 += int(correct[:k].reshape(-1).float().sum().item())
                total += targets.size(0)
        return {
            "top1": round(correct1 / max(total, 1), 5),
            "top5": round(correct5 / max(total, 1), 5),
            "val_loss": round(loss_sum / max(total, 1), 5),
        }

    def _make_plots(
        self,
        work_dir: Path,
        history: list[dict],
        model: Any,
        val_loader: Any,
        classes: list[str],
        device: str,
        memory_format: Any,
    ) -> list[Path]:
        files: list[Path] = []
        try:
            import matplotlib  # type: ignore

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt  # type: ignore
        except Exception:
            return files

        # Loss / accuracy curves.
        try:
            epochs = [h["epoch"] for h in history]
            fig, ax1 = plt.subplots(figsize=(6, 4))
            ax1.plot(epochs, [h.get("train_loss", 0) for h in history], label="train_loss")
            ax1.plot(epochs, [h.get("val_loss", 0) for h in history], label="val_loss")
            ax1.set_xlabel("epoch")
            ax1.set_ylabel("loss")
            ax2 = ax1.twinx()
            ax2.plot(epochs, [h.get("top1", 0) for h in history], "g--", label="top1")
            ax2.set_ylabel("top1")
            ax1.legend(loc="upper left")
            fig.tight_layout()
            results = work_dir / "results.png"
            fig.savefig(results)
            plt.close(fig)
            files.append(results)
        except Exception:
            pass

        # Confusion matrix from a final val pass.
        if val_loader is not None:
            try:
                import numpy as np  # type: ignore
                import torch  # type: ignore

                n = len(classes)
                cm = np.zeros((n, n), dtype=int)
                model.eval()
                with torch.no_grad():
                    for inputs, targets in val_loader:
                        inputs = inputs.to(device, memory_format=memory_format)
                        preds = model(inputs).argmax(1).cpu().numpy()
                        for t, p in zip(targets.numpy(), preds, strict=False):
                            cm[int(t)][int(p)] += 1
                fig, ax = plt.subplots(figsize=(5, 5))
                ax.imshow(cm, cmap="Blues")
                ax.set_xlabel("predicted")
                ax.set_ylabel("true")
                ax.set_xticks(range(n))
                ax.set_yticks(range(n))
                ax.set_xticklabels(classes, rotation=90, fontsize=6)
                ax.set_yticklabels(classes, fontsize=6)
                fig.tight_layout()
                cm_path = work_dir / "confusion_matrix.png"
                fig.savefig(cm_path)
                plt.close(fig)
                files.append(cm_path)
            except Exception:
                pass
        return files

    # ----------------------------------------------------------- export / infer
    def export_onnx(
        self, local_pt: Path, out_dir: Path, *, opset: int | None = None, dynamic: bool = True
    ) -> Path | None:
        import timm  # type: ignore
        import torch  # type: ignore

        ckpt = torch.load(str(local_pt), map_location="cpu", weights_only=False)
        model = self._rebuild_model(timm, ckpt)
        model.eval()
        img = int(ckpt.get("img_size", 224))
        dummy = torch.zeros(1, 3, img, img)
        out_path = out_dir / "model.onnx"
        dynamic_axes = {"input": {0: "batch"}, "output": {0: "batch"}} if dynamic else None
        torch.onnx.export(
            model,
            dummy,
            str(out_path),
            input_names=["input"],
            output_names=["output"],
            opset_version=int(opset) if opset else 17,
            dynamic_axes=dynamic_axes,
        )
        return out_path if out_path.exists() else None

    def load_predictor(self, local_pt: Path) -> Any:
        import timm  # type: ignore
        import torch  # type: ignore
        from timm.data import create_transform  # type: ignore

        ckpt = torch.load(str(local_pt), map_location="cpu", weights_only=False)
        model = self._rebuild_model(timm, ckpt)
        model.eval()
        img = int(ckpt.get("img_size", 224))
        transform = create_transform(input_size=img, is_training=False)
        return {
            "model": model,
            "transform": transform,
            "classes": ckpt.get("classes", []),
        }

    def predict_classification(self, predictor: Any, image_path: str) -> tuple[str, float]:
        import torch  # type: ignore
        from PIL import Image  # type: ignore

        model = predictor["model"]
        transform = predictor["transform"]
        classes = predictor["classes"]
        img = Image.open(image_path).convert("RGB")
        tensor = transform(img).unsqueeze(0)
        with torch.no_grad():
            probs = torch.softmax(model(tensor), dim=1)[0]
        idx = int(probs.argmax().item())
        name = classes[idx] if 0 <= idx < len(classes) else str(idx)
        return (name, float(probs[idx].item()))

    @staticmethod
    def _rebuild_model(timm_mod: Any, ckpt: dict) -> Any:
        model = timm_mod.create_model(
            ckpt.get("arch", "resnet50"),
            pretrained=False,
            num_classes=int(ckpt.get("num_classes", 1000)),
            global_pool=ckpt.get("global_pool", "avg"),
        )
        model.load_state_dict(ckpt["state_dict"])
        return model


register(TimmTrainer())
