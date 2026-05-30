from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.asset import Asset

VALID_SPLITS = ("train", "val", "test")
DEFAULT_RATIOS = (0.8, 0.2, 0.0)
DEFAULT_SEED = 42


class SplitConfigError(ValueError):
    """Raised when split ratios are invalid (negative or all-zero)."""


def asset_split(asset: Any) -> str | None:
    """Read an asset's persisted split tag (train/val/test) from meta_data JSON.

    This is the single source of truth used by both training and evaluation so
    they always agree on which assets belong to which split.
    """
    md = getattr(asset, "meta_data", None)
    if not md:
        return None
    try:
        parsed = json.loads(md) if isinstance(md, str) else md
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    val = parsed.get("split") or parsed.get("subset")
    if not val:
        return None
    val = str(val).lower()
    return val if val in VALID_SPLITS else None


def normalize_ratios(train: float, val: float, test: float) -> tuple[float, float, float]:
    """Validate and L1-normalize the three split ratios so they sum to 1.0."""
    parts = [float(train), float(val), float(test)]
    if any(p < 0 for p in parts):
        raise SplitConfigError("split ratios must be non-negative")
    total = sum(parts)
    if total <= 0:
        raise SplitConfigError("split ratios must not all be zero")
    return parts[0] / total, parts[1] / total, parts[2] / total


def resolve_split(asset_id: str, ratios: tuple[float, float, float], seed: int) -> str:
    """Deterministically assign an asset to a split via a seeded hash.

    Used as a fallback when an asset has no persisted split, so a training run is
    always reproducible regardless of whether splits were pre-assigned.
    """
    train_r, val_r, _ = ratios
    digest = hashlib.sha256(f"{seed}:{asset_id}".encode()).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    if frac < train_r:
        return "train"
    if frac < train_r + val_r:
        return "val"
    return "test"


def _dominant_class(annotations: list[Annotation]) -> str:
    """Pick the most frequent class on an asset for stratification."""
    counts: dict[str, int] = defaultdict(int)
    for ann in annotations:
        if ann.class_name:
            counts[ann.class_name] += 1
    if not counts:
        return "__none__"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _annotations_by_asset(db: Session, asset_ids: list[str]) -> dict[str, list[Annotation]]:
    out: dict[str, list[Annotation]] = defaultdict(list)
    if not asset_ids:
        return out
    rows = db.scalars(select(Annotation).where(Annotation.asset_id.in_(asset_ids))).all()
    for ann in rows:
        out[ann.asset_id].append(ann)
    return out


def _slice_counts(n: int, ratios: tuple[float, float, float]) -> tuple[int, int, int]:
    """Split ``n`` items into (train, val, test) honoring ratios with no loss."""
    train_r, val_r, _ = ratios
    n_train = int(round(n * train_r))
    n_val = int(round(n * val_r))
    # Whatever rounding left over goes to test so counts always sum to n.
    n_train = min(n_train, n)
    n_val = min(n_val, n - n_train)
    n_test = n - n_train - n_val
    return n_train, n_val, n_test


def assign_splits(
    db: Session,
    version_id: str,
    *,
    train: float = 0.8,
    val: float = 0.2,
    test: float = 0.0,
    seed: int = DEFAULT_SEED,
    stratify: bool = True,
) -> dict:
    """Deterministically assign train/val/test to every asset in a version.

    Writes the chosen split into each ``asset.meta_data`` JSON (under ``split``)
    and commits. When ``stratify`` is set, the ratio is applied within each
    dominant-class bucket so rare classes are represented in every split.
    Returns a summary identical in shape to :func:`get_split_summary`.
    """
    ratios = normalize_ratios(train, val, test)
    assets = list(db.scalars(select(Asset).where(Asset.version_id == version_id)).all())

    anns_by_asset: dict[str, list[Annotation]] = {}
    if stratify:
        anns_by_asset = _annotations_by_asset(db, [a.id for a in assets])

    # Bucket assets (single bucket when not stratifying).
    buckets: dict[str, list[Asset]] = defaultdict(list)
    for a in assets:
        key = _dominant_class(anns_by_asset.get(a.id, [])) if stratify else "__all__"
        buckets[key].append(a)

    rng = random.Random(seed)
    assignment: dict[str, str] = {}
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda a: a.id)
        rng.shuffle(group)
        n_train, n_val, _ = _slice_counts(len(group), ratios)
        for idx, a in enumerate(group):
            if idx < n_train:
                assignment[a.id] = "train"
            elif idx < n_train + n_val:
                assignment[a.id] = "val"
            else:
                assignment[a.id] = "test"

    for a in assets:
        try:
            md = json.loads(a.meta_data) if a.meta_data else {}
            if not isinstance(md, dict):
                md = {}
        except Exception:
            md = {}
        md["split"] = assignment[a.id]
        a.meta_data = json.dumps(md)
        db.add(a)
    db.commit()

    return _summarize(assets, anns_by_asset, ratios, seed, stratify)


def get_split_summary(db: Session, version_id: str) -> dict:
    """Return persisted split counts + per-class-per-split breakdown for a version."""
    assets = list(db.scalars(select(Asset).where(Asset.version_id == version_id)).all())
    anns_by_asset = _annotations_by_asset(db, [a.id for a in assets])
    return _summarize(assets, anns_by_asset, ratios=None, seed=None, stratify=None)


def _summarize(
    assets: list[Asset],
    anns_by_asset: dict[str, list[Annotation]],
    ratios: tuple[float, float, float] | None,
    seed: int | None,
    stratify: bool | None,
) -> dict:
    counts = {"train": 0, "val": 0, "test": 0, "unassigned": 0}
    # per_class[class][split] -> count
    per_class: dict[str, dict[str, int]] = defaultdict(lambda: {"train": 0, "val": 0, "test": 0})
    for a in assets:
        split = asset_split(a) or "unassigned"
        counts[split] = counts.get(split, 0) + 1
        if split in VALID_SPLITS:
            cls = _dominant_class(anns_by_asset.get(a.id, [])) if anns_by_asset else "__all__"
            per_class[cls][split] += 1

    summary: dict[str, Any] = {
        "total": len(assets),
        "counts": counts,
        "per_class": {k: v for k, v in sorted(per_class.items())},
    }
    if ratios is not None:
        summary["ratios"] = {"train": ratios[0], "val": ratios[1], "test": ratios[2]}
    if seed is not None:
        summary["seed"] = seed
    if stratify is not None:
        summary["stratify"] = stratify
    return summary
