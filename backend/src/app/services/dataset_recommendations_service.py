"""Dataset "suggested improvements" recommendations engine.

Derives a prioritized, structured list of actionable recommendations from the
existing dataset health metrics (``asset_service.get_dataset_metrics``). Pure
read-only analysis: no writes, no external calls.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.asset_service import get_dataset_metrics

# --- Thresholds (named constants) -------------------------------------------

# Class imbalance: ratio of the most- to least-represented class.
IMBALANCE_HIGH_RATIO = 10.0
IMBALANCE_MEDIUM_RATIO = 3.0

# Annotation coverage: share of assets that are still unlabeled.
UNLABELED_HIGH_FRAC = 0.50
UNLABELED_MEDIUM_FRAC = 0.20

# Empty images: share of assets carrying zero annotations.
EMPTY_IMAGE_FRAC = 0.20
EMPTY_IMAGE_MIN_COUNT = 5

# Small dataset: minimum labeled images before the set is "big enough".
SMALL_DATASET_MIN_LABELED = 100

# Tiny objects: share of sampled boxes that fall in the "small" area bucket.
TINY_BOX_FRAC = 0.50

# Resolution spread: max_pixels / min_pixels beyond which the set is "mixed".
RESOLUTION_SPREAD_RATIO = 9.0

# Review backlog: share of annotations left unreviewed.
REVIEW_BACKLOG_FRAC = 0.50
REVIEW_BACKLOG_MIN_COUNT = 20

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _safe_div(numerator: float, denominator: float) -> float:
    """Divide, returning 0.0 when the denominator is zero/falsy."""
    if not denominator:
        return 0.0
    return numerator / denominator


def _extremes(instances: dict[str, int]) -> tuple[tuple[str, int] | None, tuple[str, int] | None]:
    """Return ((max_class, max_n), (min_class, min_n)) over non-empty classes."""
    usable = [(c, n) for c, n in instances.items() if c != "(none)" and n > 0]
    if not usable:
        return None, None
    top = max(usable, key=lambda kv: kv[1])
    bottom = min(usable, key=lambda kv: kv[1])
    return top, bottom


def generate_recommendations(
    db: Session, dataset_id: str, *, version_id: str | None = None
) -> list[dict]:
    """Analyze dataset metrics and return prioritized recommendations.

    Each item: ``{id, severity, category, title, detail, metric}`` where
    ``severity`` is one of ``high | medium | low`` and ``metric`` is an optional
    supporting value. Returns ``[]`` when metrics are unavailable/empty.
    """
    try:
        m = get_dataset_metrics(db, dataset_id, version_id)
    except Exception:
        return []
    if not m:
        return []

    total_assets = m.get("total_assets") or 0
    if total_assets <= 0:
        # No imagery yet — nothing meaningful to recommend.
        return []

    recs: list[dict] = []

    # --- Class imbalance ---------------------------------------------------
    class_balance = m.get("class_balance") or {}
    instances = class_balance.get("instances") or {}
    top, bottom = _extremes(instances)
    ratio = class_balance.get("imbalance_ratio")
    if top and bottom and ratio and top[0] != bottom[0]:
        if ratio >= IMBALANCE_HIGH_RATIO:
            severity = "high"
        elif ratio >= IMBALANCE_MEDIUM_RATIO:
            severity = "medium"
        else:
            severity = None
        if severity:
            recs.append(
                {
                    "id": "class_imbalance",
                    "severity": severity,
                    "category": "class_balance",
                    "title": f"Class imbalance ({ratio}×)",
                    "detail": (
                        f"'{top[0]}' has {top[1]} instances but '{bottom[0]}' only has "
                        f"{bottom[1]}. Collect more examples of under-represented classes "
                        "or rebalance to avoid biased training."
                    ),
                    "metric": ratio,
                }
            )

    # --- Unused (defined-but-unannotated) classes --------------------------
    unused = [c for c in (class_balance.get("unused_classes") or []) if c]
    if unused:
        recs.append(
            {
                "id": "unused_classes",
                "severity": "medium",
                "category": "class_balance",
                "title": f"{len(unused)} unused class(es)",
                "detail": (
                    "Defined but never annotated: "
                    f"{', '.join(unused)}. Remove them from the class map or add "
                    "annotations for them."
                ),
                "metric": len(unused),
            }
        )

    # --- Low annotation coverage ------------------------------------------
    labeled = m.get("labeled") or 0
    unlabeled = max(total_assets - labeled, 0)
    unlabeled_frac = _safe_div(unlabeled, total_assets)
    if unlabeled > 0:
        if unlabeled_frac > UNLABELED_HIGH_FRAC:
            severity = "high"
        elif unlabeled_frac > UNLABELED_MEDIUM_FRAC:
            severity = "medium"
        else:
            severity = None
        if severity:
            recs.append(
                {
                    "id": "low_coverage",
                    "severity": severity,
                    "category": "coverage",
                    "title": f"Low annotation coverage ({round(unlabeled_frac * 100)}% unlabeled)",
                    "detail": (
                        f"Annotate the remaining {unlabeled} image(s) to improve coverage "
                        "before training."
                    ),
                    "metric": unlabeled,
                }
            )

    # --- Empty images (zero annotations) ----------------------------------
    empty_images = m.get("empty_images") or 0
    empty_frac = _safe_div(empty_images, total_assets)
    if empty_images >= EMPTY_IMAGE_MIN_COUNT and empty_frac >= EMPTY_IMAGE_FRAC:
        recs.append(
            {
                "id": "empty_images",
                "severity": "medium",
                "category": "coverage",
                "title": f"{empty_images} image(s) with no annotations",
                "detail": (
                    f"{round(empty_frac * 100)}% of images have zero annotations. Verify these "
                    "are true negatives (background) or annotate the missing objects."
                ),
                "metric": empty_images,
            }
        )

    # --- Small dataset -----------------------------------------------------
    if 0 < labeled < SMALL_DATASET_MIN_LABELED:
        recs.append(
            {
                "id": "small_dataset",
                "severity": "medium",
                "category": "dataset_size",
                "title": f"Small dataset ({labeled} labeled image(s))",
                "detail": (
                    f"Fewer than {SMALL_DATASET_MIN_LABELED} labeled images. Collect more data "
                    "to improve model generalization."
                ),
                "metric": labeled,
            }
        )

    # --- Tiny objects / box-size skew -------------------------------------
    box_geometry = m.get("box_geometry") or {}
    area_hist = box_geometry.get("area_histogram") or {}
    total_boxes = sum(area_hist.values())
    small_boxes = area_hist.get("small (<32²)", 0)
    small_frac = _safe_div(small_boxes, total_boxes)
    if total_boxes > 0 and small_frac >= TINY_BOX_FRAC:
        recs.append(
            {
                "id": "tiny_objects",
                "severity": "low",
                "category": "geometry",
                "title": f"Many tiny objects ({round(small_frac * 100)}% small boxes)",
                "detail": (
                    "A large share of boxes are very small. Consider higher-resolution "
                    "training or image tiling so small objects are detectable."
                ),
                "metric": round(small_frac, 2),
            }
        )

    # --- Resolution inconsistency -----------------------------------------
    resolution = m.get("resolution") or {}
    min_px = resolution.get("min_pixels")
    max_px = resolution.get("max_pixels")
    if min_px and max_px and _safe_div(max_px, min_px) >= RESOLUTION_SPREAD_RATIO:
        spread = round(_safe_div(max_px, min_px), 1)
        recs.append(
            {
                "id": "resolution_spread",
                "severity": "low",
                "category": "resolution",
                "title": f"Inconsistent image resolutions ({spread}× spread)",
                "detail": (
                    "Image sizes vary widely. Standardize resolution or rely on consistent "
                    "resize/letterbox settings to stabilize training."
                ),
                "metric": spread,
            }
        )

    # --- Review backlog ----------------------------------------------------
    review = m.get("review") or {}
    unreviewed = review.get("unreviewed") or 0
    total_reviewed_scope = (
        unreviewed + (review.get("approved") or 0) + (review.get("rejected") or 0)
    )
    review_frac = _safe_div(unreviewed, total_reviewed_scope)
    if unreviewed >= REVIEW_BACKLOG_MIN_COUNT and review_frac >= REVIEW_BACKLOG_FRAC:
        recs.append(
            {
                "id": "review_backlog",
                "severity": "low",
                "category": "review",
                "title": f"{unreviewed} unreviewed annotation(s)",
                "detail": (
                    f"{round(review_frac * 100)}% of annotations are unreviewed. Review them to "
                    "catch labeling errors before training."
                ),
                "metric": unreviewed,
            }
        )

    recs.sort(key=lambda r: _SEVERITY_ORDER.get(r["severity"], 99))
    return recs
