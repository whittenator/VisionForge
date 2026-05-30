from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.asset import Asset
from app.models.dataset import ClassMap, Dataset
from app.models.dataset_version import DatasetVersion

# Cap on how many annotation geometries we parse in Python for the
# size/aspect-ratio histograms. Above this we sample and flag the result.
_GEOMETRY_SAMPLE_CAP = 5000


def get_asset(db: Session, asset_id: str) -> Asset | None:
    return db.get(Asset, asset_id)


def list_assets(
    db: Session,
    dataset_id: str,
    *,
    version_id: str | None = None,
    label_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Asset], int]:
    q = select(Asset).where(Asset.dataset_id == dataset_id)
    if version_id:
        q = q.where(Asset.version_id == version_id)
    if label_status:
        q = q.where(Asset.label_status == label_status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    assets = list(db.scalars(q.offset(offset).limit(limit)).all())
    return assets, total or 0


def confirm_upload(
    db: Session,
    *,
    dataset_id: str,
    version_id: str,
    storage_key: str,
    filename: str,
    content_type: str,
    width: int | None = None,
    height: int | None = None,
) -> Asset:
    """Register an asset after successful upload to MinIO."""
    asset = Asset(
        dataset_id=dataset_id,
        version_id=version_id,
        uri=storage_key,
        mime_type=content_type or "application/octet-stream",
        width=width,
        height=height,
        label_status="unlabeled",
        meta_data=json.dumps({"filename": filename}),
    )
    db.add(asset)
    # Update asset_count on the version
    version = db.get(DatasetVersion, version_id)
    if version:
        version.asset_count = (version.asset_count or 0) + 1
        db.add(version)
    db.commit()
    db.refresh(asset)
    return asset


def get_dataset_stats(db: Session, dataset_id: str, version_id: str | None = None) -> dict:
    """Return class distribution, annotation coverage, label status breakdown."""
    q = select(Asset).where(Asset.dataset_id == dataset_id)
    if version_id:
        q = q.where(Asset.version_id == version_id)
    assets = list(db.scalars(q).all())
    asset_ids = [a.id for a in assets]

    # Label status distribution
    status_counts: dict[str, int] = {}
    for a in assets:
        status_counts[a.label_status] = status_counts.get(a.label_status, 0) + 1

    # Class distribution from annotations
    class_counts: dict[str, int] = {}
    if asset_ids:
        anns = list(db.scalars(select(Annotation).where(Annotation.asset_id.in_(asset_ids))).all())
        for ann in anns:
            cls = ann.class_name or "unlabeled"
            class_counts[cls] = class_counts.get(cls, 0) + 1

    total = len(assets)
    labeled = status_counts.get("labeled", 0) + status_counts.get("prelabeled", 0)

    return {
        "total_assets": total,
        "labeled": labeled,
        "unlabeled": status_counts.get("unlabeled", 0) + status_counts.get("unlabelled", 0),
        "in_progress": status_counts.get("in_progress", 0),
        "coverage_pct": round(labeled / total * 100, 1) if total > 0 else 0.0,
        "label_status_distribution": status_counts,
        "class_distribution": class_counts,
        "annotation_count": sum(class_counts.values()),
    }


def _box_wh(geometry_json: str) -> tuple[float, float] | None:
    """Parse a box annotation's geometry JSON into (width, height) in pixels."""
    try:
        g = json.loads(geometry_json)
    except Exception:
        return None
    w = g.get("w")
    h = g.get("h")
    if isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0:
        return float(w), float(h)
    return None


def get_dataset_metrics(db: Session, dataset_id: str, version_id: str | None = None) -> dict:
    """Gold-standard dataset health metrics.

    Aggregates in SQL where possible; geometry histograms parse a capped sample
    of annotation rows in Python. Scopes to a single version when given.
    """
    _LABELED = ("labeled", "prelabeled")

    def _scope_assets(q):
        q = q.where(Asset.dataset_id == dataset_id)
        if version_id:
            q = q.where(Asset.version_id == version_id)
        return q

    def _scope_anns(q):
        # Explicit select_from(Annotation): several callers select only column
        # expressions (counts), so SQLAlchemy can't infer the join's left side.
        q = (
            q.select_from(Annotation)
            .join(Asset, Annotation.asset_id == Asset.id)
            .where(Asset.dataset_id == dataset_id)
        )
        if version_id:
            q = q.where(Asset.version_id == version_id)
        return q

    # --- Asset / workflow counts ------------------------------------------
    status_rows = db.execute(
        _scope_assets(select(Asset.label_status, func.count())).group_by(Asset.label_status)
    ).all()
    status_counts = {s: c for s, c in status_rows}
    total_assets = sum(status_counts.values())
    labeled = sum(status_counts.get(s, 0) for s in _LABELED)

    annotated_assets = (
        db.scalar(_scope_anns(select(func.count(func.distinct(Annotation.asset_id))))) or 0
    )
    empty_images = max(total_assets - annotated_assets, 0)

    # --- Review workflow ---------------------------------------------------
    review_rows = db.execute(
        _scope_anns(select(Annotation.review_status, func.count())).group_by(
            Annotation.review_status
        )
    ).all()
    review_counts = {(s or "unreviewed"): c for s, c in review_rows}
    flagged = db.scalar(_scope_anns(select(func.count())).where(Annotation.flagged.is_(True))) or 0

    # --- Class balance -----------------------------------------------------
    instance_rows = db.execute(
        _scope_anns(select(Annotation.class_name, func.count())).group_by(Annotation.class_name)
    ).all()
    image_rows = db.execute(
        _scope_anns(
            select(Annotation.class_name, func.count(func.distinct(Annotation.asset_id)))
        ).group_by(Annotation.class_name)
    ).all()
    instance_counts = {(c or "(none)"): n for c, n in instance_rows}
    image_counts = {(c or "(none)"): n for c, n in image_rows}
    total_annotations = sum(instance_counts.values())

    nonzero = [n for c, n in instance_counts.items() if c != "(none)" and n > 0]
    imbalance_ratio = round(max(nonzero) / min(nonzero), 2) if len(nonzero) >= 1 else None

    # Defined-but-unused classes (declared in the ClassMap, never annotated).
    defined_classes: list[str] = []
    ds = db.get(Dataset, dataset_id)
    if ds and ds.class_map_id:
        cm = db.get(ClassMap, ds.class_map_id)
        if cm:
            try:
                for c in json.loads(cm.classes):
                    name = c if isinstance(c, str) else c.get("name")
                    if name:
                        defined_classes.append(name)
            except Exception:
                pass
    used = {c for c in instance_counts if c != "(none)"}
    unused_classes = [c for c in defined_classes if c not in used]

    # --- Annotation type breakdown ----------------------------------------
    type_rows = db.execute(
        _scope_anns(select(Annotation.type, func.count())).group_by(Annotation.type)
    ).all()
    type_counts = {t: n for t, n in type_rows}

    # --- Annotations per image --------------------------------------------
    per_asset_rows = db.execute(
        _scope_anns(select(Annotation.asset_id, func.count())).group_by(Annotation.asset_id)
    ).all()
    per_image_counts = [n for _, n in per_asset_rows]
    per_image_hist = {"0": empty_images, "1": 0, "2-5": 0, "6-10": 0, "10+": 0}
    for n in per_image_counts:
        if n == 1:
            per_image_hist["1"] += 1
        elif n <= 5:
            per_image_hist["2-5"] += 1
        elif n <= 10:
            per_image_hist["6-10"] += 1
        else:
            per_image_hist["10+"] += 1
    per_image_mean = round(total_annotations / total_assets, 2) if total_assets else 0.0
    per_image_max = max(per_image_counts) if per_image_counts else 0

    # --- Box geometry (area + aspect ratio), sampled ----------------------
    geo_rows = db.execute(
        _scope_anns(select(Annotation.geometry))
        .where(Annotation.type == "box")
        .limit(_GEOMETRY_SAMPLE_CAP + 1)
    ).all()
    geometry_sampled = len(geo_rows) > _GEOMETRY_SAMPLE_CAP
    area_hist = {"small (<32²)": 0, "medium (<96²)": 0, "large (≥96²)": 0}
    aspect_hist = {"tall (<0.5)": 0, "square (0.5-2)": 0, "wide (>2)": 0}
    for (geom,) in geo_rows[:_GEOMETRY_SAMPLE_CAP]:
        wh = _box_wh(geom)
        if not wh:
            continue
        w, h = wh
        area = w * h
        if area < 32 * 32:
            area_hist["small (<32²)"] += 1
        elif area < 96 * 96:
            area_hist["medium (<96²)"] += 1
        else:
            area_hist["large (≥96²)"] += 1
        ar = w / h
        if ar < 0.5:
            aspect_hist["tall (<0.5)"] += 1
        elif ar <= 2.0:
            aspect_hist["square (0.5-2)"] += 1
        else:
            aspect_hist["wide (>2)"] += 1

    # --- Image resolution --------------------------------------------------
    res_rows = db.execute(
        _scope_assets(select(Asset.width, Asset.height)).where(Asset.width.is_not(None))
    ).all()
    res_hist = {"<640": 0, "640-1280": 0, "1280-1920": 0, "≥1920": 0}
    areas: list[int] = []
    for w, h in res_rows:
        if not w or not h:
            continue
        areas.append(w * h)
        m = max(w, h)
        if m < 640:
            res_hist["<640"] += 1
        elif m < 1280:
            res_hist["640-1280"] += 1
        elif m < 1920:
            res_hist["1280-1920"] += 1
        else:
            res_hist["≥1920"] += 1
    areas.sort()
    if areas:
        median_area = areas[len(areas) // 2]
        resolution = {
            "min_pixels": areas[0],
            "max_pixels": areas[-1],
            "median_pixels": median_area,
            "histogram": res_hist,
            "with_dimensions": len(areas),
        }
    else:
        resolution = {
            "min_pixels": None,
            "max_pixels": None,
            "median_pixels": None,
            "histogram": res_hist,
            "with_dimensions": 0,
        }

    # --- Labeling velocity (last 30 days) ---------------------------------
    since = datetime.now(timezone.utc) - timedelta(days=30)
    vel_rows = db.execute(
        _scope_anns(select(func.date(Annotation.created_at), func.count()))
        .where(Annotation.created_at >= since)
        .group_by(func.date(Annotation.created_at))
    ).all()
    velocity = [{"date": str(d), "count": n} for d, n in vel_rows if d is not None]
    velocity.sort(key=lambda r: r["date"])

    coverage_pct = round(labeled / total_assets * 100, 1) if total_assets else 0.0

    return {
        "total_assets": total_assets,
        "total_annotations": total_annotations,
        "coverage_pct": coverage_pct,
        "labeled": labeled,
        "empty_images": empty_images,
        "label_status_distribution": status_counts,
        "review": {
            "unreviewed": review_counts.get("unreviewed", 0),
            "approved": review_counts.get("approved", 0),
            "rejected": review_counts.get("rejected", 0),
            "flagged": flagged,
        },
        "class_balance": {
            "instances": instance_counts,
            "images": image_counts,
            "imbalance_ratio": imbalance_ratio,
            "defined_classes": defined_classes,
            "unused_classes": unused_classes,
        },
        "annotation_types": type_counts,
        "per_image": {
            "histogram": per_image_hist,
            "mean": per_image_mean,
            "max": per_image_max,
        },
        "box_geometry": {
            "area_histogram": area_hist,
            "aspect_histogram": aspect_hist,
            "sampled": geometry_sampled,
        },
        "resolution": resolution,
        "velocity": velocity,
        "split": None,  # train/val/test split not modeled yet
    }
