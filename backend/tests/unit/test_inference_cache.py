"""Tests for the in-process inference LRU cache.

We don't load a real model — just exercise the cache plumbing with stubs.
"""

from app.services import inference_service


class _Artifact:
    def __init__(self, id_: str):
        self.id = id_
        self.storage_path = f"/tmp/{id_}.pt"
        self.format = "pytorch"
        self.type = "yolo"


def test_evict_and_clear_dont_raise():
    inference_service.evict("missing")
    inference_service._cache.clear()  # type: ignore[attr-defined]
    assert inference_service.cache_stats()["size"] == 0


def test_lru_eviction_when_full(monkeypatch):
    loaded: list[str] = []

    def fake_load(artifact):
        loaded.append(artifact.id)
        return ("yolo", object())

    monkeypatch.setattr(inference_service, "_load_artifact", fake_load)
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
    monkeypatch.setattr(inference_service, "_load_artifact", lambda art: ("yolo", sentinel))
    a = _Artifact("x")
    first = inference_service._cache.get_or_load(a)
    second = inference_service._cache.get_or_load(a)
    assert first is second
