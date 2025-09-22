from __future__ import annotations

import math
from collections.abc import Iterable


def select_uncertain(scores: Iterable[float], k: int) -> list[int]:
    # Higher score = more uncertain
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    return [i for i, _ in indexed[:k]]


def l2(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def select_diverse(embeddings: list[list[float]], k: int) -> list[int]:
    # Greedy furthest-point sampling
    if not embeddings:
        return []
    n = len(embeddings)
    selected: list[int] = [0]
    dists = [0.0] * n
    for _ in range(1, min(k, n)):
        last = embeddings[selected[-1]]
        for i, e in enumerate(embeddings):
            d = l2(e, last)
            dists[i] = max(dists[i], d)
        next_idx = max(range(n), key=lambda i: dists[i] if i not in selected else -1)
        if next_idx in selected:
            break
        selected.append(next_idx)
    return selected
