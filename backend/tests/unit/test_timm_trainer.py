"""Tests for the Timm trainer.

The capability-schema test is dependency-free. The training smoke test actually
runs a 1-epoch CPU fit and is skipped unless torch/timm/torchvision/PIL are
installed (e.g. on the GPU agent images / full backend env).
"""

import io
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.services import training as training_pkg
from app.services.training.base import TrainContext


def test_timm_capabilities_cover_full_surface():
    caps = training_pkg.get_trainer("timm").capabilities().to_dict()
    titles = {g["title"] for g in caps["groups"]}
    assert {"Architecture", "Core", "Optimizer", "Schedule", "Regularization", "Augmentation"} <= (
        titles
    )
    all_keys = {f["key"] for g in caps["groups"] for f in g["fields"]}
    # A representative slice of the full hyperparameter / augmentation surface.
    for key in ("model", "global_pool", "opt", "sched", "mixup", "aa", "reprob", "model_ema"):
        assert key in all_keys


@dataclass
class _Asset:
    id: str
    uri: str
    width: int = 32
    height: int = 32


@dataclass
class _Ann:
    class_name: str
    geometry: str = "{}"
    type: str = "classification"


def _png_bytes(color):
    from PIL import Image  # type: ignore

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, format="PNG")
    return buf.getvalue()


def test_timm_cpu_smoke_train(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("timm")
    pytest.importorskip("torchvision")
    pytest.importorskip("PIL")

    class _Resp:
        def __init__(self, data):
            self._d = data

        def read(self):
            return self._d

        def close(self):
            pass

        def release_conn(self):
            pass

    class _Minio:
        def get_object(self, bucket, key):
            color = (255, 0, 0) if "cat" in key else (0, 0, 255)
            return _Resp(_png_bytes(color))

    assets, anns, splits = [], {}, {}
    for i in range(6):
        label = "cat" if i % 2 == 0 else "dog"
        a = _Asset(f"a{i}", f"s3://b/{label}{i}.png")
        assets.append(a)
        anns[a.id] = [_Ann(label)]
        splits[a.id] = "train" if i < 4 else "val"

    captured = []

    def report(progress=None, epoch=None):
        if epoch is not None:
            captured.append(epoch)

    ctx = TrainContext(
        db=None,
        run=None,
        params={
            "model": "resnet10t",
            "pretrained": False,
            "epochs": 1,
            "batch_size": 2,
            "img_size": 32,
            "num_workers": 0,
            "amp": False,
            "device": "cpu",
            "sched": "none",
        },
        task="classify",
        class_names=["cat", "dog"],
        assets=assets,
        annotations_by_asset=anns,
        splits=splits,
        minio_client=_Minio(),
        bucket="b",
        work_dir=tmp_path,
        report=report,
    )

    result = training_pkg.get_trainer("timm").run(ctx)
    assert result.best_model_path and Path(result.best_model_path).exists()
    assert result.artifact_meta["arch"] == "resnet10t"
    assert result.artifact_meta["classes"] == ["cat", "dog"]
    assert captured and "top1" in captured[0]

    # The saved checkpoint is self-describing so export/inference can rebuild it.
    import torch  # type: ignore

    ckpt = torch.load(str(result.best_model_path), map_location="cpu", weights_only=False)
    assert ckpt["vf_framework"] == "timm"
    assert ckpt["classes"] == ["cat", "dog"]
