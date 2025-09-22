from __future__ import annotations

from collections.abc import Iterable


class EmbeddingsService:
    def __init__(self):
        self._impl = None
        try:  # optional heavy imports
            import torch  # noqa: F401
            from open_clip import create_model_and_transforms, get_tokenizer  # type: ignore
            self._impl = (create_model_and_transforms, get_tokenizer)
        except Exception:
            self._impl = None

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        # Fallback: deterministic dummy embeddings for tests without heavy deps
        embs: list[list[float]] = []
        for t in texts:
            h = abs(hash(t)) % 1000
            embs.append([h / 1000.0, (h % 97) / 97.0, (h % 89) / 89.0])
        return embs
