"""In-process model serving with a small LRU cache.

A first cut: load Ultralytics YOLO or ONNX models from MinIO/HTTP/local on
demand, keep up to N in memory. Good for prototyping and low-RPS use; will be
fronted by Triton in a later phase.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models.artifact import ModelArtifact

# Cap on how many models live in memory simultaneously.
MAX_MODELS = int(os.getenv("VF_INFERENCE_CACHE_SIZE", "3"))


class InferenceError(Exception):
    pass


@dataclass
class _CacheEntry:
    kind: str
    model: Any
    scratch_dir: Path  # the tempdir holding the downloaded weights


class _ModelCache:
    """LRU cache keyed by artifact id. Thread-safe."""

    def __init__(self, max_size: int = MAX_MODELS) -> None:
        self.max_size = max_size
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get_or_load(self, artifact: ModelArtifact) -> tuple[str, Any]:
        with self._lock:
            key = artifact.id
            entry = self._cache.get(key)
            if entry is not None:
                self._cache.move_to_end(key)
                return (entry.kind, entry.model)
            kind, model, scratch = _load_artifact(artifact)
            self._cache[key] = _CacheEntry(kind=kind, model=model, scratch_dir=scratch)
            while len(self._cache) > self.max_size:
                _, dropped = self._cache.popitem(last=False)
                _safe_rmtree(dropped.scratch_dir)
            return (kind, model)

    def evict(self, artifact_id: str) -> None:
        with self._lock:
            entry = self._cache.pop(artifact_id, None)
            if entry is not None:
                _safe_rmtree(entry.scratch_dir)

    def clear(self) -> None:
        with self._lock:
            for entry in self._cache.values():
                _safe_rmtree(entry.scratch_dir)
            self._cache.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "loaded": list(self._cache.keys()),
            }


def _safe_rmtree(path: Path) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


_cache = _ModelCache()


def cache_stats() -> dict[str, Any]:
    return _cache.stats()


def evict(artifact_id: str) -> None:
    _cache.evict(artifact_id)


def predict(
    artifact: ModelArtifact,
    image_bytes: bytes,
    *,
    score_threshold: float = 0.25,
) -> dict[str, Any]:
    """Run the cached model on a single image (raw bytes). Returns predictions dict."""
    kind, model = _cache.get_or_load(artifact)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(image_bytes)
        img_path = f.name
    try:
        if kind == "yolo":
            return _yolo_predict(model, img_path, score_threshold)
        if kind == "onnx":
            return _onnx_predict(model, img_path, score_threshold)
        raise InferenceError(f"unsupported model kind: {kind}")
    finally:
        try:
            os.unlink(img_path)
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Loaders / runners (lazy ML imports)
# ----------------------------------------------------------------------------


def _load_artifact(artifact: ModelArtifact) -> tuple[str, Any, Path]:
    """Returns (kind, model, scratch_dir). Caller owns cleanup of scratch_dir."""
    storage_path = artifact.storage_path
    if not storage_path:
        raise InferenceError("artifact has no storage_path")

    scratch = Path(tempfile.mkdtemp(prefix="vf-model-"))
    local = scratch / Path(storage_path).name
    if not _download_to(storage_path, local):
        _safe_rmtree(scratch)
        raise InferenceError(f"could not fetch artifact at {storage_path}")

    fmt = (artifact.format or artifact.type or "").lower()
    if fmt == "onnx" or str(local).endswith(".onnx"):
        try:
            import onnxruntime as ort  # type: ignore
        except Exception as exc:  # pragma: no cover
            _safe_rmtree(scratch)
            raise InferenceError("onnxruntime not installed") from exc
        return (
            "onnx",
            ort.InferenceSession(str(local), providers=["CPUExecutionProvider"]),
            scratch,
        )

    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:  # pragma: no cover
        _safe_rmtree(scratch)
        raise InferenceError("ultralytics not installed") from exc
    return ("yolo", YOLO(str(local)), scratch)


def _download_to(uri: str, dest: Path) -> bool:
    try:
        if uri.startswith(("http://", "https://")):
            import urllib.request

            urllib.request.urlretrieve(uri, str(dest))  # noqa: S310
            return True
        if os.path.exists(uri):
            import shutil

            shutil.copy(uri, dest)
            return True
        from app.services.storage import get_minio_client

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        client = get_minio_client()
        client.fget_object(bucket, uri, str(dest))
        return True
    except Exception:
        return False


def _yolo_predict(model: Any, img_path: str, score_threshold: float) -> dict[str, Any]:
    results = model.predict(img_path, conf=score_threshold, verbose=False)
    detections: list[dict[str, Any]] = []
    classification: dict[str, Any] | None = None
    for r in results:
        names = getattr(r, "names", {}) or {}
        boxes = getattr(r, "boxes", None)
        if boxes is not None:
            for box in boxes:
                cls_idx = int(box.cls.item()) if hasattr(box, "cls") else 0
                xy = box.xywh[0].tolist() if hasattr(box, "xywh") else [0, 0, 0, 0]
                cx, cy, w, h = xy
                detections.append(
                    {
                        "class": names.get(cls_idx, str(cls_idx)),
                        "bbox": [cx - w / 2, cy - h / 2, w, h],
                        "score": float(box.conf.item()) if hasattr(box, "conf") else 0.0,
                    }
                )
        probs = getattr(r, "probs", None)
        if probs is not None:
            top = int(probs.top1)
            classification = {
                "class": names.get(top, str(top)),
                "score": float(probs.top1conf.item()),
            }
    out: dict[str, Any] = {"detections": detections}
    if classification:
        out["classification"] = classification
    return out


def _onnx_predict(session: Any, img_path: str, score_threshold: float) -> dict[str, Any]:
    """Generic ONNX runner — assumes a single image input. Returns raw logits."""
    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise InferenceError("numpy/Pillow not installed") from exc

    inputs = session.get_inputs()
    if not inputs:
        return {"raw": []}
    input_name = inputs[0].name
    shape = inputs[0].shape
    h = shape[2] if len(shape) >= 3 and isinstance(shape[2], int) else 224
    w = shape[3] if len(shape) >= 4 and isinstance(shape[3], int) else 224

    img = Image.open(img_path).convert("RGB").resize((w, h))
    arr = np.asarray(img, dtype="float32").transpose(2, 0, 1) / 255.0
    arr = arr[np.newaxis, ...]
    outputs = session.run(None, {input_name: arr})
    # Best-effort softmax of first output if it looks like logits
    logits = outputs[0]
    flat = logits.reshape(-1)
    exp = np.exp(flat - np.max(flat))
    probs = (exp / exp.sum()).tolist()
    top_idx = int(np.argmax(flat))
    return {
        "raw_shape": list(logits.shape),
        "top_class_index": top_idx,
        "top_score": float(probs[top_idx]) if probs else 0.0,
        "score_threshold": score_threshold,
    }
