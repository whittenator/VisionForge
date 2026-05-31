"""Unit tests for the shared dataset exporters."""

from dataclasses import dataclass

from app.services.training import datasets


@dataclass
class _Asset:
    id: str
    uri: str
    width: int = 64
    height: int = 64


@dataclass
class _Ann:
    class_name: str
    geometry: str = "{}"
    type: str = "classification"


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        pass

    def release_conn(self):
        pass


class _FakeMinio:
    """Returns a tiny fixed byte payload for any object."""

    def get_object(self, bucket, key):
        return _FakeResponse(b"\x89PNG\r\n")


def test_build_imagefolder_layout_and_test_holdout(tmp_path):
    assets = [
        _Asset("a1", "s3://b/cat1.png"),
        _Asset("a2", "s3://b/dog1.png"),
        _Asset("a3", "s3://b/cat2.png"),
        _Asset("a4", "s3://b/secret.png"),
    ]
    anns = {
        "a1": [_Ann("cat")],
        "a2": [_Ann("dog")],
        "a3": [_Ann("cat")],
        "a4": [_Ann("dog")],
    }
    splits = {"a1": "train", "a2": "train", "a3": "val", "a4": "test"}

    root = datasets.build_imagefolder(
        assets, anns, ["cat", "dog"], tmp_path, _FakeMinio(), "b", splits
    )

    # train/cat + train/dog populated, val/cat populated.
    assert (root / "train" / "cat" / "a1.png").exists()
    assert (root / "train" / "dog" / "a2.png").exists()
    assert (root / "val" / "cat" / "a3.png").exists()
    # The test asset is held out entirely — never written anywhere.
    assert not list(root.rglob("a4.png"))


def test_build_yolo_detect_writes_labels_and_yaml(tmp_path):
    assets = [_Asset("a1", "s3://b/img.png", width=100, height=100)]
    anns = {"a1": [_Ann("cat", geometry='{"x1": 10, "y1": 10, "x2": 50, "y2": 50}', type="box")]}
    splits = {"a1": "train"}

    data_yaml = datasets.build_yolo_detect(
        assets, anns, ["cat", "dog"], tmp_path, _FakeMinio(), "b", splits
    )
    assert data_yaml.name == "data.yaml"
    label = (tmp_path / "train" / "labels" / "a1.txt").read_text().strip()
    # class index 0 (cat); center (0.3,0.3), size (0.4,0.4).
    parts = label.split()
    assert parts[0] == "0"
    assert abs(float(parts[1]) - 0.3) < 1e-3
    assert abs(float(parts[3]) - 0.4) < 1e-3
