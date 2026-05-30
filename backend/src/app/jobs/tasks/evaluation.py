"""Celery task: evaluate a trained model artifact against a dataset version.

Runs the artifact (PyTorch / ONNX) over labeled assets in the requested split,
computes summary metrics, per-class P/R/F1, a confusion matrix, and a sample
of false positives / false negatives for the FP/FN viewer.

Heavy ML deps (ultralytics, torch, onnxruntime) are imported lazily so the
module is safe to load in test environments where those wheels are absent.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover

    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn

        return _wrap


def _make_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _iou(box_a: tuple[float, ...], box_b: tuple[float, ...]) -> float:
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, aw) * max(0.0, ah)
    area_b = max(0.0, bw) * max(0.0, bh)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def compute_classification_metrics(
    pairs: list[tuple[str, str]], classes: list[str]
) -> dict[str, Any]:
    """Build accuracy + per-class P/R/F1 + confusion matrix from (pred, gt) pairs."""
    n = len(pairs)
    if n == 0:
        return {
            "metrics": {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
            "per_class": {},
            "confusion": [[0] * len(classes) for _ in classes],
            "classes": classes,
        }
    idx = {c: i for i, c in enumerate(classes)}
    matrix = [[0 for _ in classes] for _ in classes]
    correct = 0
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = defaultdict(int)
    for pred, gt in pairs:
        if gt in idx:
            support[gt] += 1
        if pred == gt:
            correct += 1
            if pred in idx:
                tp[pred] += 1
                matrix[idx[gt]][idx[pred]] += 1
        else:
            if pred in idx:
                fp[pred] += 1
            if gt in idx:
                fn[gt] += 1
            if pred in idx and gt in idx:
                matrix[idx[gt]][idx[pred]] += 1

    per_class: dict[str, Any] = {}
    macro_p = macro_r = macro_f1 = 0.0
    counted = 0
    for c in classes:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        per_class[c] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "support": support[c],
        }
        if support[c] > 0:
            macro_p += p
            macro_r += r
            macro_f1 += f1
            counted += 1

    if counted > 0:
        macro_p /= counted
        macro_r /= counted
        macro_f1 /= counted

    return {
        "metrics": {
            "accuracy": round(correct / n, 4),
            "precision": round(macro_p, 4),
            "recall": round(macro_r, 4),
            "f1": round(macro_f1, 4),
            "samples": n,
        },
        "per_class": per_class,
        "confusion": matrix,
        "classes": classes,
    }


def _ap_from_pr(pr_data: list[tuple[float, int]], npos: int) -> float:
    """11-point interpolated AP from a (score_desc, is_tp) list."""
    if npos <= 0:
        return 0.0
    rows = sorted(pr_data, key=lambda x: -x[0])
    cum_tp = cum_fp = 0
    recalls = [0.0]
    precisions = [1.0]
    for _score, is_tp in rows:
        if is_tp:
            cum_tp += 1
        else:
            cum_fp += 1
        recall = cum_tp / npos
        prec = cum_tp / max(1, cum_tp + cum_fp)
        recalls.append(recall)
        precisions.append(prec)
    ap = 0.0
    for t in [i / 10 for i in range(11)]:
        valid = [precisions[i] for i in range(len(recalls)) if recalls[i] >= t]
        ap += max(valid) if valid else 0.0
    return ap / 11.0


def compute_detection_ap_at_iou(
    items: list[dict[str, Any]], classes: list[str], iou_threshold: float
) -> dict[str, float]:
    """Per-class AP at a single IoU threshold. Returns {class: ap}."""
    pr_data: dict[str, list[tuple[float, int]]] = defaultdict(list)
    pr_npos: dict[str, int] = defaultdict(int)
    for item in items:
        gts = list(item.get("gt") or [])
        preds = sorted(item.get("pred") or [], key=lambda p: -float(p.get("score", 0.0)))
        for g in gts:
            if g.get("class") in classes:
                pr_npos[g["class"]] += 1
        used = [False] * len(gts)
        for p in preds:
            cls = p.get("class")
            best_j = -1
            best_iou = 0.0
            for j, g in enumerate(gts):
                if used[j] or g.get("class") != cls:
                    continue
                iou = _iou(tuple(p["bbox"]), tuple(g["bbox"]))
                if iou > best_iou:
                    best_iou = iou
                    best_j = j
            if best_j >= 0 and best_iou >= iou_threshold:
                used[best_j] = True
                pr_data[cls].append((float(p.get("score", 0.0)), 1))
            else:
                pr_data[cls].append((float(p.get("score", 0.0)), 0))
    return {c: _ap_from_pr(pr_data.get(c, []), pr_npos.get(c, 0)) for c in classes}


def compute_detection_metrics(
    items: list[dict[str, Any]],
    classes: list[str],
    *,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Compute detection mAP@iou + per-class P/R/F1 + confusion matrix.

    `items` is a list of {asset_id, gt: [{class, bbox}], pred: [{class, bbox, score}]}.
    bbox is (x, y, w, h) in pixel space.
    Also computes mAP@[.5:.95] (10-point) for COCO-style reporting.
    """
    idx = {c: i for i, c in enumerate(classes)}
    matrix = [[0 for _ in classes] for _ in classes]
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = defaultdict(int)

    # AP@iou via interpolated PR per class
    pr_data: dict[str, list[tuple[float, int]]] = defaultdict(list)  # (score, is_tp)
    pr_npos: dict[str, int] = defaultdict(int)

    for item in items:
        gts = list(item.get("gt") or [])
        preds = sorted(item.get("pred") or [], key=lambda p: -float(p.get("score", 0.0)))
        for cls in {g.get("class") for g in gts}:
            if cls in idx:
                pr_npos[cls] += sum(1 for g in gts if g.get("class") == cls)
        for g in gts:
            if g.get("class") in idx:
                support[g["class"]] += 1

        # ---- Pass 1: class-STRICT matching for TP / FP / FN / AP ----
        # Each prediction is greedily matched to the highest-IoU same-class GT
        # above the threshold. This is the standard mAP@iou definition.
        used_strict = [False] * len(gts)
        for p in preds:
            best_j = -1
            best_iou = 0.0
            for j, g in enumerate(gts):
                if used_strict[j]:
                    continue
                if g.get("class") != p.get("class"):
                    continue
                iou = _iou(tuple(p["bbox"]), tuple(g["bbox"]))
                if iou > best_iou:
                    best_iou = iou
                    best_j = j
            cls = p.get("class")
            if best_j >= 0 and best_iou >= iou_threshold:
                used_strict[best_j] = True
                if cls in idx:
                    tp[cls] += 1
                pr_data[cls].append((float(p.get("score", 0.0)), 1))
            else:
                if cls in idx:
                    fp[cls] += 1
                pr_data[cls].append((float(p.get("score", 0.0)), 0))
        for j, g in enumerate(gts):
            if not used_strict[j]:
                cls = g.get("class")
                if cls in idx:
                    fn[cls] += 1

        # ---- Pass 2: class-AGNOSTIC matching for the confusion matrix ----
        # Match each prediction to its best-IoU GT regardless of class so we
        # can record off-diagonal cells (predicted X when ground truth was Y).
        used_any = [False] * len(gts)
        for p in preds:
            best_j = -1
            best_iou = 0.0
            for j, g in enumerate(gts):
                if used_any[j]:
                    continue
                iou = _iou(tuple(p["bbox"]), tuple(g["bbox"]))
                if iou > best_iou:
                    best_iou = iou
                    best_j = j
            if best_j >= 0 and best_iou >= iou_threshold:
                used_any[best_j] = True
                pred_cls = p.get("class")
                gt_cls = gts[best_j].get("class")
                if pred_cls in idx and gt_cls in idx:
                    matrix[idx[gt_cls]][idx[pred_cls]] += 1

    per_class: dict[str, Any] = {}
    macro_p = macro_r = macro_f1 = macro_ap = 0.0
    counted = 0
    for c in classes:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        # AP@iou: sort by score desc and integrate
        rows = sorted(pr_data[c], key=lambda x: -x[0])
        cum_tp = cum_fp = 0
        recalls = [0.0]
        precisions = [1.0]
        npos = pr_npos.get(c, 0) or 1
        for _score, is_tp in rows:
            if is_tp:
                cum_tp += 1
            else:
                cum_fp += 1
            recall = cum_tp / npos
            prec = cum_tp / max(1, cum_tp + cum_fp)
            recalls.append(recall)
            precisions.append(prec)
        # 11-point interpolation
        ap = 0.0
        for t in [i / 10 for i in range(11)]:
            valid = [precisions[i] for i in range(len(recalls)) if recalls[i] >= t]
            ap += max(valid) if valid else 0.0
        ap /= 11.0
        per_class[c] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "support": support[c],
            "ap50": round(ap, 4),
        }
        if support[c] > 0:
            macro_p += p
            macro_r += r
            macro_f1 += f1
            macro_ap += ap
            counted += 1

    if counted > 0:
        macro_p /= counted
        macro_r /= counted
        macro_f1 /= counted
        macro_ap /= counted

    # mAP@[.5:.95] — average of mAP at IoU thresholds 0.50, 0.55, ..., 0.95.
    # Each threshold is computed against the same items so behaviour matches
    # COCO. ``mAP50`` is always tied to IoU=0.50 (per the canonical definition);
    # ``mAP_at_iou`` carries the metric at the caller-supplied threshold so
    # downstream consumers can reason about both without naming collisions.
    iou_thresholds = [round(0.50 + 0.05 * i, 2) for i in range(10)]
    map_per_iou: dict[str, float] = {}
    sum_map = 0.0
    counted_iou = 0
    for thr in iou_thresholds:
        per_cls = compute_detection_ap_at_iou(items, classes, thr)
        valid = [v for c, v in per_cls.items() if support[c] > 0]
        m = sum(valid) / len(valid) if valid else 0.0
        map_per_iou[f"mAP_{int(thr * 100):02d}"] = round(m, 4)
        sum_map += m
        counted_iou += 1
    map_5095 = sum_map / counted_iou if counted_iou else 0.0
    map50 = map_per_iou.get("mAP_50", round(macro_ap, 4))

    # mAP at the caller-selected IoU. If the caller passed a non-grid value
    # (anything outside .5/.55/.../.95) compute it on demand so we still
    # report the metric they asked for.
    iou_key = f"mAP_{int(iou_threshold * 100):02d}"
    if iou_key in map_per_iou:
        map_at_iou = map_per_iou[iou_key]
    else:
        per_cls_caller = compute_detection_ap_at_iou(items, classes, iou_threshold)
        valid_caller = [v for c, v in per_cls_caller.items() if support[c] > 0]
        map_at_iou = round(sum(valid_caller) / len(valid_caller) if valid_caller else 0.0, 4)

    return {
        "metrics": {
            # Canonical mAP definitions — always tied to their fixed IoU.
            "mAP50": map50,
            "mAP_5095": round(map_5095, 4),
            # The caller-selected threshold, separately keyed so it never
            # silently shadows ``mAP50`` for non-0.5 callers.
            "mAP_at_iou": map_at_iou,
            "iou_threshold": iou_threshold,
            **map_per_iou,
            "precision": round(macro_p, 4),
            "recall": round(macro_r, 4),
            "f1": round(macro_f1, 4),
            "samples": len(items),
        },
        "per_class": per_class,
        "confusion": matrix,
        "classes": classes,
    }


def _download_to(uri: str, dest: Path) -> bool:
    """Download an asset URI (S3 key, http URL, or local path) to dest."""
    try:
        if uri.startswith(("http://", "https://")):
            import urllib.request

            urllib.request.urlretrieve(uri, str(dest))  # noqa: S310
            return True
        if os.path.exists(uri):
            import shutil

            shutil.copy(uri, dest)
            return True
        # Treat as MinIO key
        from app.services.storage import get_minio_client

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        client = get_minio_client()
        client.fget_object(bucket, uri, str(dest))
        return True
    except Exception:
        return False


def _asset_split(asset) -> str | None:
    """Read the asset's split tag (test/val/train) from its meta_data JSON."""
    md = getattr(asset, "meta_data", None)
    if not md:
        return None
    try:
        parsed = json.loads(md)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    val = parsed.get("split") or parsed.get("subset")
    return str(val).lower() if val else None


def _load_classes_for_dataset(db, version) -> list[str]:
    from app.models.dataset import ClassMap, Dataset

    dataset = db.get(Dataset, version.dataset_id)
    if dataset and dataset.class_map_id:
        cm = db.get(ClassMap, dataset.class_map_id)
        if cm and cm.classes:
            try:
                classes = json.loads(cm.classes)
                if isinstance(classes, list) and classes:
                    return [str(c) for c in classes]
            except Exception:
                pass
    return []


@shared_task(name="app.jobs.tasks.evaluation.evaluate_task")
def evaluate_task(payload: dict) -> dict:
    """Run the eval. Returns a status dict; persists results to the Evaluation row."""
    job_id = payload.get("jobId")
    eval_id = payload.get("evaluationId")
    artifact_id = payload.get("artifactId")
    version_id = payload.get("datasetVersionId")
    score_threshold = float(payload.get("scoreThreshold", 0.25))
    iou_threshold = float(payload.get("iouThreshold", 0.5))
    sample_budget = int(payload.get("sampleFpFnCount", 50))
    max_samples = int(payload.get("maxSamples", 0)) or None
    split = (payload.get("split") or "all").lower()

    db = _make_session()
    try:
        from app.models.annotation import Annotation
        from app.models.artifact import ModelArtifact
        from app.models.asset import Asset
        from app.models.dataset_version import DatasetVersion
        from app.services.evaluation_service import write_result
        from app.services.jobs_service import update_job_status

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)
        write_result(db, eval_id, status="running")

        artifact = db.get(ModelArtifact, artifact_id)
        version = db.get(DatasetVersion, version_id)
        if not artifact or not version:
            raise RuntimeError("artifact or dataset version not found")

        classes = _load_classes_for_dataset(db, version)
        if not classes:
            classes = ["object"]

        # Pull labeled assets in this version
        from sqlalchemy import select

        assets = list(
            db.scalars(
                select(Asset).where(
                    Asset.version_id == version.id,
                    Asset.label_status.in_(("labeled", "prelabeled")),
                )
            ).all()
        )
        # Apply split filter. We look in `meta_data.split` (set by the importers /
        # annotation tools). When "all", every labeled asset is in scope; when a
        # specific split is requested but no asset carries that tag, we fall back
        # to "all" rather than silently scoring zero samples.
        if split and split != "all":
            tagged = [a for a in assets if _asset_split(a) == split]
            if tagged:
                assets = tagged
        if max_samples:
            assets = assets[:max_samples]
        if not assets:
            write_result(
                db,
                eval_id,
                status="succeeded",
                metrics={"samples": 0},
                per_class={},
                confusion=[[0] * len(classes) for _ in classes],
                classes=classes,
                samples=[],
            )
            if job_id:
                update_job_status(db, job_id, status="succeeded", progress=1.0)
            return {"status": "succeeded", "samples": 0}

        # Determine task: detection if any annotation has type "box", else classification
        first_asset_anns = list(
            db.scalars(
                select(Annotation).where(Annotation.asset_id.in_([a.id for a in assets[:50]]))
            ).all()
        )
        is_detection = any(a.type == "box" for a in first_asset_anns)

        # Single per-task scratch dir — cleans up the downloaded weights when we
        # exit the `with` block, regardless of success/failure.
        scratch_ctx = tempfile.TemporaryDirectory()
        scratch_dir = Path(scratch_ctx.name)
        model = _load_model(artifact, scratch_dir)

        if is_detection:
            items: list[dict[str, Any]] = []
            samples: list[dict[str, Any]] = []
            for i, asset in enumerate(assets):
                anns = list(
                    db.scalars(select(Annotation).where(Annotation.asset_id == asset.id)).all()
                )
                gts = []
                for a in anns:
                    if a.type != "box":
                        continue
                    try:
                        g = json.loads(a.geometry)
                        gts.append(
                            {
                                "class": a.class_name or "object",
                                "bbox": (
                                    g.get("x", 0),
                                    g.get("y", 0),
                                    g.get("w", 0),
                                    g.get("h", 0),
                                ),
                            }
                        )
                    except Exception:
                        continue

                preds = _predict_detections(model, asset, score_threshold)
                items.append({"asset_id": asset.id, "gt": gts, "pred": preds})

                # Build FP/FN samples (cap)
                if len(samples) < sample_budget:
                    used = [False] * len(gts)
                    for p in preds:
                        match_j = -1
                        match_iou = 0.0
                        for j, g in enumerate(gts):
                            if used[j]:
                                continue
                            if g["class"] != p["class"]:
                                continue
                            iou = _iou(tuple(p["bbox"]), tuple(g["bbox"]))
                            if iou > match_iou:
                                match_iou = iou
                                match_j = j
                        if match_j >= 0 and match_iou >= iou_threshold:
                            used[match_j] = True
                        else:
                            samples.append(
                                {
                                    "asset_id": asset.id,
                                    "predicted": p["class"],
                                    "ground_truth": None,
                                    "score": p.get("score"),
                                    "kind": "fp",
                                }
                            )
                            if len(samples) >= sample_budget:
                                break
                    for j, g in enumerate(gts):
                        if not used[j] and len(samples) < sample_budget:
                            samples.append(
                                {
                                    "asset_id": asset.id,
                                    "predicted": None,
                                    "ground_truth": g["class"],
                                    "kind": "fn",
                                }
                            )

                if job_id and i % 10 == 0:
                    update_job_status(
                        db,
                        job_id,
                        status="running",
                        progress=0.1 + 0.85 * (i / len(assets)),
                    )

            result = compute_detection_metrics(items, classes, iou_threshold=iou_threshold)
            write_result(
                db,
                eval_id,
                status="succeeded",
                metrics=result["metrics"],
                per_class=result["per_class"],
                confusion=result["confusion"],
                classes=classes,
                samples=samples,
            )
        else:
            pairs: list[tuple[str, str]] = []
            samples = []
            for i, asset in enumerate(assets):
                anns = list(
                    db.scalars(select(Annotation).where(Annotation.asset_id == asset.id)).all()
                )
                gt_cls: str | None = None
                for a in anns:
                    if a.type == "classification":
                        gt_cls = a.class_name
                        break
                if gt_cls is None:
                    continue
                pred_cls, score = _predict_classification(model, asset, classes)
                pairs.append((pred_cls, gt_cls))
                if pred_cls != gt_cls and len(samples) < sample_budget:
                    samples.append(
                        {
                            "asset_id": asset.id,
                            "predicted": pred_cls,
                            "ground_truth": gt_cls,
                            "score": score,
                            "kind": "fp",
                        }
                    )
                if job_id and i % 10 == 0:
                    update_job_status(
                        db,
                        job_id,
                        status="running",
                        progress=0.1 + 0.85 * (i / len(assets)),
                    )

            result = compute_classification_metrics(pairs, classes)
            write_result(
                db,
                eval_id,
                status="succeeded",
                metrics=result["metrics"],
                per_class=result["per_class"],
                confusion=result["confusion"],
                classes=classes,
                samples=samples,
            )

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)
        return {"status": "succeeded"}

    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        try:
            from app.services.evaluation_service import write_result as _wr
            from app.services.jobs_service import update_job_status as _us

            _wr(db, eval_id, status="failed", error_message=msg)
            if job_id:
                _us(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
        return {"status": "failed", "error": msg}
    finally:
        try:
            scratch_ctx.cleanup()
        except (UnboundLocalError, NameError, FileNotFoundError):
            pass
        db.close()


def _load_model(artifact, scratch_dir: Path) -> Any:
    """Lazy model loader. Downloads weights into `scratch_dir` (caller-managed).

    Returns ``(kind, predictor)`` where ``kind`` is ``"onnx"`` or the framework
    key (e.g. ``"ultralytics"``, ``"timm"``). Framework dispatch goes through the
    trainer registry so no library name is hard-coded here.
    """
    storage_path = artifact.storage_path
    if not storage_path:
        raise RuntimeError("artifact has no storage_path")
    local = scratch_dir / Path(storage_path).name
    if not _download_to(storage_path, local):
        raise RuntimeError(f"could not fetch artifact from {storage_path}")
    fmt = (artifact.format or artifact.type or "").lower()
    if fmt == "onnx" or str(local).endswith(".onnx"):
        import onnxruntime as ort  # type: ignore

        return (
            "onnx",
            ort.InferenceSession(str(local), providers=["CPUExecutionProvider"]),
        )
    from app.services import training as training_pkg

    framework = getattr(artifact, "framework", None)
    trainer = training_pkg.get_trainer(framework)
    return (trainer.key, trainer.load_predictor(local))


def _predict_detections(model, asset, score_threshold: float) -> list[dict[str, Any]]:
    kind, m = model
    if kind == "onnx":
        return []
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "img"
        if not _download_to(asset.uri, img_path):
            return []
        from app.services import training as training_pkg

        try:
            return training_pkg.get_trainer(kind).predict_detections(
                m, str(img_path), score_threshold
            )
        except NotImplementedError:
            return []


def _predict_classification(model, asset, classes: list[str]) -> tuple[str, float]:
    kind, m = model
    if kind == "onnx":
        return ("unknown", 0.0)
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "img"
        if not _download_to(asset.uri, img_path):
            return ("unknown", 0.0)
        from app.services import training as training_pkg

        try:
            return training_pkg.get_trainer(kind).predict_classification(m, str(img_path))
        except NotImplementedError:
            return ("unknown", 0.0)
