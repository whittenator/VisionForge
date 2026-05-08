"""Tests for the in-process inference LRU cache.

We don't load a real model — just exercise the cache plumbing with stubs.
"""

import tempfile
from pathlib import Path

from app.services import inference_service


class _Artifact:
    def __init__(self, id_: str):
        self.id = id_
        self.storage_path = f"/tmp/{id_}.pt"
        self.format = "pytorch"
        self.type = "yolo"


def _stub_load(artifact):
    """Pretend to load: returns (kind, model, scratch_dir) like the real loader."""
    scratch = Path(tempfile.mkdtemp(prefix="vf-test-model-"))
    return ("yolo", object(), scratch)


def test_evict_and_clear_dont_raise():
    inference_service.evict("missing")
    inference_service._cache.clear()  # type: ignore[attr-defined]
    assert inference_service.cache_stats()["size"] == 0


def test_lru_eviction_when_full(monkeypatch):
    monkeypatch.setattr(inference_service, "_load_artifact", _stub_load)
    monkeypatch.setattr(inference_service._cache, "max_size", 2)
    inference_service._cache.clear()  # type: ignore[attr-defined]

    inference_service._cache.get_or_load(_Artifact("a"))
    inference_service._cache.get_or_load(_Artifact("b"))
    inference_service._cache.get_or_load(_Artifact("c"))

    stats = inference_service.cache_stats()
    assert stats["size"] == 2
    # 'a' should be evicted; 'b' + 'c' remain
    assert "a" not in stats["loaded"]


def test_get_returns_same_instance_within_capacity(monkeypatch):
    inference_service._cache.clear()  # type: ignore[attr-defined]
    monkeypatch.setattr(inference_service._cache, "max_size", 4)
    sentinel = object()
    sentinel_scratch = Path(tempfile.mkdtemp(prefix="vf-test-model-"))
    monkeypatch.setattr(
        inference_service, "_load_artifact", lambda art: ("yolo", sentinel, sentinel_scratch)
    )
    a = _Artifact("x")
    first_kind, first_model = inference_service._cache.get_or_load(a)
    second_kind, second_model = inference_service._cache.get_or_load(a)
    assert first_kind == second_kind == "yolo"
    assert first_model is second_model is sentinel


def test_evict_cleans_scratch_dir(monkeypatch, tmp_path):
    """Evicting a cached entry must remove its on-disk scratch dir."""
    inference_service._cache.clear()  # type: ignore[attr-defined]
    monkeypatch.setattr(inference_service._cache, "max_size", 2)

    created: list[Path] = []

    def stub(artifact):
        d = Path(tempfile.mkdtemp(prefix="vf-test-evict-", dir=tmp_path))
        # Drop a file so the dir isn't empty
        (d / "weights.pt").write_bytes(b"x")
        created.append(d)
        return ("yolo", object(), d)

    monkeypatch.setattr(inference_service, "_load_artifact", stub)
    inference_service._cache.get_or_load(_Artifact("e1"))
    assert created[-1].exists()
    inference_service.evict("e1")
    assert not created[-1].exists()
