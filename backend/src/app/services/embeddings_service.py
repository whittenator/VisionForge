from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterable


class EmbeddingsService:
    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "openai"

    def __init__(self) -> None:
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._dim = 512  # ViT-B-32 embedding dim
        self._try_load()

    def _try_load(self) -> None:
        try:
            import open_clip  # type: ignore
            import torch  # noqa: F401

            model, _, preprocess = open_clip.create_model_and_transforms(
                self.MODEL_NAME, pretrained=self.PRETRAINED
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer(self.MODEL_NAME)
            self._model = model
            self._preprocess = preprocess
            self._tokenizer = tokenizer
        except Exception:
            pass

    def embed_images(self, image_paths: Iterable[str]) -> list[list[float]]:
        """Embed images using open-clip. Falls back to hash if model not available."""
        paths = list(image_paths)
        if self._model is None or self._preprocess is None:
            return [self._hash_fallback(p) for p in paths]

        import torch

        results: list[list[float]] = []
        for path in paths:
            try:
                from PIL import Image  # type: ignore

                img = Image.open(path).convert("RGB")
                tensor = self._preprocess(img).unsqueeze(0)  # type: ignore[arg-type]
                with torch.no_grad():
                    features = self._model.encode_image(tensor)
                    features = features / features.norm(dim=-1, keepdim=True)
                results.append(features[0].tolist())
            except Exception:
                results.append(self._hash_fallback(path))
        return results

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        """Embed texts using open-clip tokenizer. Falls back to hash if not available."""
        text_list = list(texts)
        if self._model is None or self._tokenizer is None:
            return [self._hash_fallback(t) for t in text_list]

        import torch

        results: list[list[float]] = []
        for text in text_list:
            try:
                tokens = self._tokenizer([text])
                with torch.no_grad():
                    features = self._model.encode_text(tokens)
                    features = features / features.norm(dim=-1, keepdim=True)
                results.append(features[0].tolist())
            except Exception:
                results.append(self._hash_fallback(text))
        return results

    def _hash_fallback(self, key: str, dim: int | None = None) -> list[float]:
        """Deterministic hash-based fallback embedding."""
        target_dim = dim if dim is not None else self._dim
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        # Tile the digest to cover target_dim floats (4 bytes each)
        needed_bytes = target_dim * 4
        tiled = (digest * (needed_bytes // len(digest) + 1))[:needed_bytes]
        raw = list(struct.unpack(f"{target_dim}f", tiled))
        # Normalize to unit vector to mimic real embeddings
        norm = sum(v * v for v in raw) ** 0.5 or 1.0
        return [v / norm for v in raw]
