from __future__ import annotations

import json
import logging
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset

logger = logging.getLogger(__name__)

# Hard cap on how many embedded assets we pull into memory for the pure-Python
# (SQLite / no-pgvector) paths. Keeps the O(n^2) duplicate scan bounded.
MAX_SCAN_ASSETS = 2000


def _is_postgres(db: Session) -> bool:
    """Return True when the session is bound to a PostgreSQL engine."""
    try:
        return db.get_bind().dialect.name == "postgresql"
    except Exception:  # pragma: no cover - defensive
        return False


def _as_list(value: object) -> list[float] | None:
    """Coerce a stored embedding into a plain list of floats.

    On PostgreSQL pgvector returns a list/ndarray already; on SQLite the
    ``EmbeddingVector`` decorator hands back a parsed list, but tolerate a raw
    JSON string just in case.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    try:
        return [float(v) for v in value]  # type: ignore[union-attr]
    except (TypeError, ValueError):
        return None


def _cosine_distance(a: list[float], b: list[float]) -> float | None:
    """Cosine distance (1 - cosine similarity); None when undefined."""
    if len(a) != len(b):
        return None
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return None
    return 1.0 - (dot / (math.sqrt(na) * math.sqrt(nb)))


def find_similar(
    db: Session,
    asset_id: str,
    *,
    k: int = 20,
    dataset_id: str | None = None,
) -> list[tuple[Asset, float]]:
    """Return the ``k`` nearest assets to ``asset_id`` by cosine distance.

    The query asset itself is excluded, only assets with a non-null embedding
    are considered, and results are scoped to ``dataset_id`` when supplied.
    """
    asset = db.get(Asset, asset_id)
    if asset is None:
        return []
    query_vec = _as_list(asset.embedding)
    if not query_vec:
        return []

    if _is_postgres(db):
        try:
            return _find_similar_pg(db, asset, query_vec, k, dataset_id)
        except Exception:  # pragma: no cover - fall back on any pgvector issue
            logger.warning("pgvector similarity failed; using python fallback", exc_info=True)
    return _find_similar_python(db, asset, query_vec, k, dataset_id)


def _find_similar_pg(
    db: Session,
    asset: Asset,
    query_vec: list[float],
    k: int,
    dataset_id: str | None,
) -> list[tuple[Asset, float]]:
    dist = Asset.embedding.cosine_distance(query_vec)  # type: ignore[attr-defined]
    stmt = (
        select(Asset, dist.label("distance"))
        .where(Asset.embedding.isnot(None))
        .where(Asset.id != asset.id)
    )
    if dataset_id is not None:
        stmt = stmt.where(Asset.dataset_id == dataset_id)
    stmt = stmt.order_by(dist).limit(k)
    return [(row[0], float(row[1])) for row in db.execute(stmt).all()]


def _find_similar_python(
    db: Session,
    asset: Asset,
    query_vec: list[float],
    k: int,
    dataset_id: str | None,
) -> list[tuple[Asset, float]]:
    stmt = select(Asset).where(Asset.embedding.isnot(None)).where(Asset.id != asset.id)
    if dataset_id is not None:
        stmt = stmt.where(Asset.dataset_id == dataset_id)
    candidates = db.scalars(stmt.limit(MAX_SCAN_ASSETS)).all()

    scored: list[tuple[Asset, float]] = []
    for cand in candidates:
        vec = _as_list(cand.embedding)
        if not vec:
            continue
        dist = _cosine_distance(query_vec, vec)
        if dist is None:
            continue
        scored.append((cand, dist))
    scored.sort(key=lambda item: item[1])
    return scored[:k]


def find_duplicates(
    db: Session,
    dataset_id: str,
    *,
    threshold: float = 0.05,
    max_pairs: int = 500,
) -> dict:
    """Return near-duplicate asset pairs within a dataset.

    A pair qualifies when its cosine distance is ``<= threshold``. Returns a
    dict with ``pairs`` (each ``{asset_a, asset_b, distance}``), ``total``,
    ``computed`` (False when fewer than two embeddings exist), and
    ``truncated`` (True when the dataset exceeded ``MAX_SCAN_ASSETS``).
    """
    stmt = (
        select(Asset)
        .where(Asset.dataset_id == dataset_id)
        .where(Asset.embedding.isnot(None))
        .limit(MAX_SCAN_ASSETS + 1)
    )
    assets = list(db.scalars(stmt).all())
    truncated = len(assets) > MAX_SCAN_ASSETS
    if truncated:
        logger.warning(
            "find_duplicates truncated dataset %s scan at %d assets", dataset_id, MAX_SCAN_ASSETS
        )
        assets = assets[:MAX_SCAN_ASSETS]

    parsed: list[tuple[Asset, list[float]]] = []
    for a in assets:
        vec = _as_list(a.embedding)
        if vec:
            parsed.append((a, vec))

    computed = len(parsed) >= 2
    pairs: list[dict] = []
    if computed:
        for i in range(len(parsed)):
            asset_a, vec_a = parsed[i]
            for j in range(i + 1, len(parsed)):
                asset_b, vec_b = parsed[j]
                dist = _cosine_distance(vec_a, vec_b)
                if dist is None or dist > threshold:
                    continue
                pairs.append({"asset_a": asset_a, "asset_b": asset_b, "distance": dist})
        pairs.sort(key=lambda p: p["distance"])
        pairs = pairs[:max_pairs]

    return {
        "pairs": pairs,
        "total": len(pairs),
        "computed": computed,
        "truncated": truncated,
    }
