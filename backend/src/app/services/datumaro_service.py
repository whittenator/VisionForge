"""Dataset import/export.

Native (no-dep) handlers for COCO and YOLO formats, plus a Datumaro-backed
path for everything else (Pascal VOC, CVAT, LabelMe, …) when the optional
`datumaro` package is installed.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.asset import Asset
from app.models.dataset import ClassMap, Dataset
from app.models.dataset_version import DatasetVersion

# ----------------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------------

SUPPORTED_FORMATS = ("coco", "yolo", "pascal_voc", "cvat", "labelme", "datumaro")


@dataclass
class ImportSummary:
    asset_count: int
    annotation_count: int
    classes: list[str]
    warnings: list[str]


class DatumaroError(Exception):
    pass


# ----------------------------------------------------------------------------
# Import
# ----------------------------------------------------------------------------


def import_archive(
    db: Session,
    *,
    dataset_id: str,
    version_id: str,
    archive_bytes: bytes,
    fmt: str,
    image_uri_base: str = "",
) -> ImportSummary:
    """Import a dataset archive (zip) into the dataset version.

    `image_uri_base` lets the caller prefix asset URIs (e.g. with the MinIO
    storage key for the uploaded archive) so the platform can reference the
    images later.
    """
    fmt = (fmt or "coco").lower()
    if fmt not in SUPPORTED_FORMATS:
        raise DatumaroError(f"unsupported format: {fmt}")

    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise DatumaroError("dataset not found")
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise DatumaroError("dataset version not found")

    with tempfile.TemporaryDirectory() as tmp:
        archive_dir = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            _safe_extract(zf, archive_dir)

        if fmt == "coco":
            return _import_coco(db, dataset, version, archive_dir, image_uri_base)
        if fmt == "yolo":
            return _import_yolo(db, dataset, version, archive_dir, image_uri_base)
        return _import_via_datumaro(
            db, dataset, version, archive_dir, fmt, image_uri_base
        )


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract a zip safely.

    For each member: validate that the resolved target stays under `dest`,
    skip directory entries (we mkdir as needed), and refuse symlinks
    altogether. We then write each file ourselves rather than calling
    `zf.extractall`, which avoids any TOCTOU between validation and
    extraction.
    """
    dest_resolved = dest.resolve()
    for member in zf.infolist():
        # Refuse symlinks: their target is the link path, not the file content,
        # and the OS would resolve them at follow time.
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise DatumaroError(f"unsafe symlink in archive: {member.filename!r}")

        # Build and verify the target path.
        target = (dest / member.filename).resolve()
        try:
            target.relative_to(dest_resolved)
        except ValueError as exc:
            raise DatumaroError(f"unsafe path in archive: {member.filename!r}") from exc

        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member, "r") as src, target.open("wb") as out:
            # 1 MB chunks
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)


def _import_coco(
    db: Session,
    dataset: Dataset,
    version: DatasetVersion,
    root: Path,
    image_uri_base: str,
) -> ImportSummary:
    json_files = list(root.rglob("*.json"))
    if not json_files:
        raise DatumaroError("no COCO JSON found")
    coco_path = json_files[0]
    with coco_path.open() as f:
        coco = json.load(f)

    cats = coco.get("categories") or []
    class_id_to_name: dict[int, str] = {
        c["id"]: c.get("name") or str(c["id"]) for c in cats
    }
    classes = [c.get("name") for c in cats if c.get("name")]
    _persist_classes(db, dataset, classes)

    image_id_to_asset: dict[int, str] = {}
    asset_count = 0
    warnings: list[str] = []

    for img in coco.get("images") or []:
        file_name = img.get("file_name") or ""
        width = img.get("width") or 0
        height = img.get("height") or 0
        uri = _join_uri(image_uri_base, file_name)
        asset = Asset(
            dataset_id=dataset.id,
            version_id=version.id,
            uri=uri,
            mime_type=_guess_mime(file_name),
            width=width,
            height=height,
            label_status="labeled",
            meta_data=json.dumps(
                {"filename": file_name, "coco_image_id": img.get("id")}
            ),
        )
        db.add(asset)
        db.flush()
        image_id_to_asset[int(img["id"])] = asset.id
        asset_count += 1

    annotation_count = 0
    for ann in coco.get("annotations") or []:
        asset_id = image_id_to_asset.get(int(ann.get("image_id", -1)))
        if not asset_id:
            warnings.append(f"orphan annotation image_id={ann.get('image_id')}")
            continue
        cat_id = int(ann.get("category_id", -1))
        cls = class_id_to_name.get(cat_id, "object")
        bbox = ann.get("bbox") or []
        if len(bbox) == 4:
            x, y, w, h = bbox
            geom = {"x": x, "y": y, "w": w, "h": h}
            atype = "box"
        elif ann.get("segmentation"):
            seg = ann["segmentation"]
            poly = seg[0] if isinstance(seg, list) and seg else []
            points = [
                {"x": poly[i], "y": poly[i + 1]} for i in range(0, len(poly) - 1, 2)
            ]
            geom = {"points": points}
            atype = "polygon"
        else:
            continue
        a = Annotation(
            asset_id=asset_id,
            type=atype,
            geometry=json.dumps(geom),
            class_name=cls,
            author_id=_system_user_id(),
        )
        db.add(a)
        annotation_count += 1

    version.asset_count = (version.asset_count or 0) + asset_count
    db.add(version)
    db.commit()
    return ImportSummary(asset_count, annotation_count, classes, warnings)


def _import_yolo(
    db: Session,
    dataset: Dataset,
    version: DatasetVersion,
    root: Path,
    image_uri_base: str,
) -> ImportSummary:
    """YOLO layout: images/<split>/*.jpg, labels/<split>/*.txt, classes.txt or data.yaml."""
    classes: list[str] = []
    classes_file = next(
        (p for p in root.rglob("classes.txt")),
        None,
    )
    if classes_file:
        classes = [
            line.strip()
            for line in classes_file.read_text().splitlines()
            if line.strip()
        ]
    else:
        yaml_path = next((p for p in root.rglob("data.yaml")), None)
        if yaml_path:
            for line in yaml_path.read_text().splitlines():
                if line.strip().startswith("names:"):
                    rest = line.split(":", 1)[1].strip()
                    if rest.startswith("["):
                        rest = rest.strip("[]")
                        classes = [
                            c.strip().strip("'\"") for c in rest.split(",") if c.strip()
                        ]
    if not classes:
        classes = ["object"]
    _persist_classes(db, dataset, classes)

    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in root.rglob("*") if p.suffix.lower() in image_exts]

    asset_count = 0
    annotation_count = 0
    warnings: list[str] = []
    for img_path in images:
        # Find matching label
        rel = img_path.relative_to(root)
        candidates = [
            root / Path(str(rel).replace("images", "labels")).with_suffix(".txt"),
            img_path.with_suffix(".txt"),
        ]
        label_path = next((c for c in candidates if c.exists()), None)

        try:
            from PIL import Image  # type: ignore

            with Image.open(img_path) as im:
                w, h = im.size
        except Exception:
            w, h = 0, 0

        uri = _join_uri(image_uri_base, str(rel))
        asset = Asset(
            dataset_id=dataset.id,
            version_id=version.id,
            uri=uri,
            mime_type=_guess_mime(img_path.name),
            width=w,
            height=h,
            label_status="labeled" if label_path else "unlabelled",
            meta_data=json.dumps({"filename": img_path.name}),
        )
        db.add(asset)
        db.flush()
        asset_count += 1

        if not label_path:
            continue
        for line in label_path.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                cls_idx = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:5])
            except ValueError:
                warnings.append(f"bad YOLO line: {line}")
                continue
            cls = (
                classes[cls_idx] if 0 <= cls_idx < len(classes) else f"class_{cls_idx}"
            )
            x = (cx - bw / 2) * (w or 1)
            y = (cy - bh / 2) * (h or 1)
            ww = bw * (w or 1)
            hh = bh * (h or 1)
            a = Annotation(
                asset_id=asset.id,
                type="box",
                geometry=json.dumps({"x": x, "y": y, "w": ww, "h": hh}),
                class_name=cls,
                author_id=_system_user_id(),
            )
            db.add(a)
            annotation_count += 1

    version.asset_count = (version.asset_count or 0) + asset_count
    db.add(version)
    db.commit()
    return ImportSummary(asset_count, annotation_count, classes, warnings)


def _import_via_datumaro(
    db: Session,
    dataset: Dataset,
    version: DatasetVersion,
    root: Path,
    fmt: str,
    image_uri_base: str,
) -> ImportSummary:
    try:
        import datumaro as dm  # type: ignore
    except Exception as exc:
        raise DatumaroError(
            f"format '{fmt}' requires the optional 'datumaro' package"
        ) from exc

    project = dm.Dataset.import_from(str(root), fmt)
    classes = [c for c in project.categories().get("label", dm.LabelCategories()).items]
    classes = [c.name for c in classes] if classes else []
    _persist_classes(db, dataset, classes)

    asset_count = 0
    annotation_count = 0
    warnings: list[str] = []
    for item in project:
        media = getattr(item, "media", None)
        path = getattr(media, "path", None) if media else None
        size = getattr(media, "size", None) if media else None
        w, h = (size[1], size[0]) if size else (0, 0)

        uri = _join_uri(image_uri_base, str(path) if path else item.id)
        asset = Asset(
            dataset_id=dataset.id,
            version_id=version.id,
            uri=uri,
            mime_type=_guess_mime(uri),
            width=w,
            height=h,
            label_status="labeled" if item.annotations else "unlabelled",
            meta_data=json.dumps({"filename": str(path) if path else item.id}),
        )
        db.add(asset)
        db.flush()
        asset_count += 1
        for a in item.annotations:
            geom: dict[str, Any] | None = None
            atype: str | None = None
            cls = (
                project.categories()
                .get("label", dm.LabelCategories())
                .items[a.label]
                .name
                if hasattr(a, "label") and a.label is not None
                else "object"
            )
            if a.type == dm.AnnotationType.bbox:
                geom = {"x": a.x, "y": a.y, "w": a.w, "h": a.h}
                atype = "box"
            elif a.type == dm.AnnotationType.polygon:
                pts = a.points
                points = [
                    {"x": pts[i], "y": pts[i + 1]} for i in range(0, len(pts) - 1, 2)
                ]
                geom = {"points": points}
                atype = "polygon"
            elif a.type == dm.AnnotationType.label:
                geom = {"class": cls}
                atype = "classification"
            else:
                warnings.append(f"unsupported annotation type {a.type}")
                continue
            db.add(
                Annotation(
                    asset_id=asset.id,
                    type=atype,
                    geometry=json.dumps(geom),
                    class_name=cls,
                    author_id=_system_user_id(),
                )
            )
            annotation_count += 1

    version.asset_count = (version.asset_count or 0) + asset_count
    db.add(version)
    db.commit()
    return ImportSummary(asset_count, annotation_count, classes, warnings)


# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------


def export_archive(
    db: Session,
    *,
    dataset_id: str,
    version_id: str,
    fmt: str,
) -> bytes:
    """Build a zip archive of the dataset version in the requested format.
    Returns the raw zip bytes.
    """
    fmt = (fmt or "coco").lower()
    if fmt not in SUPPORTED_FORMATS:
        raise DatumaroError(f"unsupported format: {fmt}")
    dataset = db.get(Dataset, dataset_id)
    version = db.get(DatasetVersion, version_id)
    if not dataset or not version:
        raise DatumaroError("dataset or version not found")

    classes = _load_classes(db, dataset)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if fmt == "coco":
            zf.writestr(
                "annotations.json",
                json.dumps(_build_coco(db, dataset, version, classes), indent=2),
            )
        elif fmt == "yolo":
            zf.writestr("classes.txt", "\n".join(classes))
            # Mapping from asset.id → exported label filename. We'd love to use
            # the original filename stem (so a YOLO consumer can match
            # `images/foo.jpg` ↔ `labels/foo.txt`), but two assets can share
            # the same stem (e.g. `train/img_0001.jpg` and `val/img_0001.jpg`).
            # We disambiguate by suffixing a short slice of the asset id when a
            # collision is detected. A `manifest.csv` records the mapping so
            # downstream consumers can reconstruct the original layout.
            used_stems: dict[str, str] = {}  # stem → asset_id
            manifest_rows: list[str] = ["asset_id,uri,label_file"]
            for asset, anns in _iter_assets_with_annotations(db, version):
                w = asset.width or 1
                h = asset.height or 1
                lines = []
                for a in anns:
                    if a.type != "box":
                        continue
                    try:
                        g = json.loads(a.geometry)
                    except Exception:
                        continue
                    cx = (g.get("x", 0) + g.get("w", 0) / 2) / w
                    cy = (g.get("y", 0) + g.get("h", 0) / 2) / h
                    bw = g.get("w", 0) / w
                    bh = g.get("h", 0) / h
                    cls_idx = (
                        classes.index(a.class_name) if a.class_name in classes else 0
                    )
                    lines.append(f"{cls_idx} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                base_stem = Path(asset.uri).stem or asset.id
                stem = base_stem
                if stem in used_stems and used_stems[stem] != asset.id:
                    stem = f"{base_stem}__{asset.id[:8]}"
                used_stems[stem] = asset.id
                label_file = f"labels/{stem}.txt"
                zf.writestr(label_file, "\n".join(lines))
                manifest_rows.append(f"{asset.id},{asset.uri},{label_file}")
            zf.writestr("manifest.csv", "\n".join(manifest_rows))
        else:
            # Fall back to Datumaro for non-trivial formats
            try:
                import datumaro as dm  # type: ignore
            except Exception as exc:
                raise DatumaroError(
                    f"format '{fmt}' requires the optional 'datumaro' package"
                ) from exc
            with tempfile.TemporaryDirectory() as out_dir:
                ds = _build_datumaro_dataset(db, dataset, version, classes, dm)
                ds.export(out_dir, fmt)
                # Zip the directory
                for root, _dirs, files in os.walk(out_dir):
                    for f in files:
                        p = Path(root) / f
                        zf.write(p, p.relative_to(out_dir))
    return buf.getvalue()


def _build_coco(
    db: Session,
    dataset: Dataset,
    version: DatasetVersion,
    classes: list[str],
) -> dict[str, Any]:
    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    categories = [{"id": i + 1, "name": c} for i, c in enumerate(classes)]
    cls_to_id = {c["name"]: c["id"] for c in categories}

    ann_id = 1
    for asset, anns in _iter_assets_with_annotations(db, version):
        meta = {}
        if asset.meta_data:
            try:
                meta = json.loads(asset.meta_data)
            except Exception:
                pass
        images.append(
            {
                "id": len(images) + 1,
                "file_name": meta.get("filename") or Path(asset.uri).name,
                "width": asset.width,
                "height": asset.height,
            }
        )
        img_id = len(images)
        for a in anns:
            if a.type == "box":
                try:
                    g = json.loads(a.geometry)
                except Exception:
                    continue
                annotations.append(
                    {
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cls_to_id.get(a.class_name or "", 1),
                        "bbox": [
                            g.get("x", 0),
                            g.get("y", 0),
                            g.get("w", 0),
                            g.get("h", 0),
                        ],
                        "area": g.get("w", 0) * g.get("h", 0),
                        "iscrowd": 0,
                    }
                )
                ann_id += 1
            elif a.type == "polygon":
                try:
                    g = json.loads(a.geometry)
                except Exception:
                    continue
                points = g.get("points") or []
                flat = [v for p in points for v in (p.get("x", 0), p.get("y", 0))]
                annotations.append(
                    {
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cls_to_id.get(a.class_name or "", 1),
                        "segmentation": [flat],
                        "bbox": _bbox_of_polygon(points),
                        "area": _polygon_area(points),
                        "iscrowd": 0,
                    }
                )
                ann_id += 1
    return {"images": images, "annotations": annotations, "categories": categories}


def _build_datumaro_dataset(
    db: Session,
    dataset: Dataset,
    version: DatasetVersion,
    classes: list[str],
    dm: Any,
) -> Any:  # pragma: no cover - exercised only with datumaro installed
    items = []
    cats = dm.LabelCategories.from_iterable(classes)
    for asset, anns in _iter_assets_with_annotations(db, version):
        ann_objs = []
        for a in anns:
            try:
                g = json.loads(a.geometry)
            except Exception:
                continue
            label = classes.index(a.class_name) if a.class_name in classes else 0
            if a.type == "box":
                ann_objs.append(
                    dm.Bbox(
                        g.get("x", 0),
                        g.get("y", 0),
                        g.get("w", 0),
                        g.get("h", 0),
                        label=label,
                    )
                )
            elif a.type == "polygon":
                pts = []
                for p in g.get("points") or []:
                    pts.extend([p.get("x", 0), p.get("y", 0)])
                ann_objs.append(dm.Polygon(pts, label=label))
            elif a.type == "classification":
                ann_objs.append(dm.Label(label=label))
        items.append(
            dm.DatasetItem(
                id=Path(asset.uri).stem,
                annotations=ann_objs,
                media=dm.Image(
                    path=asset.uri, size=(asset.height or 0, asset.width or 0)
                ),
            )
        )
    return dm.Dataset.from_iterable(items, categories={dm.AnnotationType.label: cats})


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _persist_classes(db: Session, dataset: Dataset, classes: list[str]) -> None:
    if not classes:
        return
    if dataset.class_map_id:
        cm = db.get(ClassMap, dataset.class_map_id)
        if cm:
            existing: list[str] = []
            try:
                existing = json.loads(cm.classes or "[]")
            except Exception:
                existing = []
            merged = list(dict.fromkeys([*existing, *classes]))
            cm.classes = json.dumps(merged)
            db.add(cm)
            return
    cm = ClassMap(project_id=dataset.project_id, classes=json.dumps(classes))
    db.add(cm)
    db.flush()
    dataset.class_map_id = cm.id
    db.add(dataset)


def _load_classes(db: Session, dataset: Dataset) -> list[str]:
    if not dataset.class_map_id:
        return []
    cm = db.get(ClassMap, dataset.class_map_id)
    if not cm or not cm.classes:
        return []
    try:
        return json.loads(cm.classes)
    except Exception:
        return []


def _iter_assets_with_annotations(
    db: Session, version: DatasetVersion
) -> Iterator[tuple[Asset, list[Annotation]]]:
    from sqlalchemy import select

    assets = list(db.scalars(select(Asset).where(Asset.version_id == version.id)).all())
    for asset in assets:
        anns = list(
            db.scalars(select(Annotation).where(Annotation.asset_id == asset.id)).all()
        )
        yield asset, anns


def _system_user_id() -> str:
    return os.getenv("VF_SYSTEM_USER_ID", "system")


def _guess_mime(name: str) -> str:
    n = name.lower()
    if n.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if n.endswith(".png"):
        return "image/png"
    if n.endswith(".webp"):
        return "image/webp"
    if n.endswith(".bmp"):
        return "image/bmp"
    if n.endswith((".mp4", ".mov", ".avi", ".webm")):
        return "video/mp4"
    return "application/octet-stream"


def _join_uri(base: str, suffix: str) -> str:
    if not base:
        return suffix
    if base.endswith("/"):
        return base + suffix.lstrip("/")
    return f"{base}/{suffix.lstrip('/')}"


def _bbox_of_polygon(points: list[dict[str, float]]) -> list[float]:
    if not points:
        return [0, 0, 0, 0]
    xs = [p.get("x", 0) for p in points]
    ys = [p.get("y", 0) for p in points]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def _polygon_area(points: list[dict[str, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        x1 = points[i].get("x", 0)
        y1 = points[i].get("y", 0)
        x2 = points[(i + 1) % n].get("x", 0)
        y2 = points[(i + 1) % n].get("y", 0)
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0
