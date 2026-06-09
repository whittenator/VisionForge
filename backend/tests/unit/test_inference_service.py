"""Unit tests for ``services/inference_service`` beyond the LRU cache.

Focuses on the download helper, the load-error path, and the ``predict``
dispatch + temp-file cleanup. The cache is pre-seeded and the per-framework
runners are stubbed so no ML wheels are needed.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

from app.services import inference_service
from app.services.inference_service import InferenceError, _CacheEntry


class _Artifact:
    def __init__(self, *, storage_path=None, fmt="pytorch", type_="yolo"):
        self.id = uuid.uuid4().hex
        self.storage_path = storage_path
        self.format = fmt
        self.type = type_
        self.framework = None


def test_download_to_copies_local_file(tmp_path):
    src = tmp_path / "weights.pt"
    src.write_bytes(b"weights")
    dest = tmp_path / "out.pt"
    assert inference_service._download_to(str(src), dest) is True
    assert dest.read_bytes() == b"weights"


def test_download_to_missing_source_returns_false(tmp_path):
    dest = tmp_path / "out.pt"
    assert inference_service._download_to(str(tmp_path / "nope.pt"), dest) is False


def test_load_artifact_without_storage_path_raises():
    with pytest.raises(InferenceError):
        inference_service._load_artifact(_Artifact(storage_path=None))


def test_predict_dispatches_to_yolo_runner_and_cleans_tempfile(monkeypatch):
    inference_service._cache.clear()
    artifact = _Artifact()
    scratch = Path(tempfile.mkdtemp(prefix="vf-test-"))
    # Seed the cache so get_or_load never tries to download/load a real model.
    inference_service._cache._cache[artifact.id] = _CacheEntry(
        kind="ultralytics", model=object(), scratch_dir=scratch
    )

    captured: dict = {}

    def fake_yolo(model, img_path, score_threshold):
        captured["img_path"] = img_path
        # The temp image must exist while the runner is executing.
        assert os.path.exists(img_path)
        return {"detections": [{"class": "cat", "bbox": [0, 0, 1, 1], "score": 0.9}]}

    monkeypatch.setattr(inference_service, "_yolo_predict", fake_yolo)

    out = inference_service.predict(artifact, b"fake-image-bytes")
    assert out["detections"][0]["class"] == "cat"
    # The scratch image is removed once predict returns.
    assert not os.path.exists(captured["img_path"])


def test_predict_dispatches_to_onnx_runner(monkeypatch):
    inference_service._cache.clear()
    artifact = _Artifact(fmt="onnx", type_="onnx")
    scratch = Path(tempfile.mkdtemp(prefix="vf-test-"))
    inference_service._cache._cache[artifact.id] = _CacheEntry(
        kind="onnx", model=object(), scratch_dir=scratch
    )
    monkeypatch.setattr(inference_service, "_onnx_predict", lambda m, p, t: {"top_class_index": 7})

    out = inference_service.predict(artifact, b"img")
    assert out["top_class_index"] == 7
