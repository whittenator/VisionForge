"""Shared dataset exporters used by the training backends.

Extracted from the original inline ``_build_yolo_dataset`` so multiple trainers
can reuse them. ``build_imagefolder`` produces the standard ImageFolder layout
used by both Ultralytics-classify and Timm; ``build_yolo_detect`` produces the
YOLO detection layout (images + label txts + ``data.yaml``).

In both, assets whose resolved split is ``"test"`` are held out entirely so the
test set stays a true unseen set for evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def extract_minio_key(uri: str) -> str:
    """Extract the object key from an asset URI (strips bucket prefix if present)."""
    for prefix in ("s3://", "minio://"):
        if uri.startswith(prefix):
            parts = uri[len(prefix) :].split("/", 1)
            return parts[1] if len(parts) > 1 else uri
    if uri.startswith("http://") or uri.startswith("https://"):
        path = uri.split("/", 3)
        return path[3] if len(path) > 3 else uri
    return uri


def fetch_image_bytes(minio_client: Any, bucket: str, asset: Any) -> bytes | None:
    """Download an asset's bytes from MinIO, or None if unavailable."""
    if minio_client is None:
        return None
    try:
        key = extract_minio_key(asset.uri)
        response = minio_client.get_object(bucket, key)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except Exception:
        return None


def build_imagefolder(
    assets: list[Any],
    annotations_by_asset: dict[str, list[Any]],
    class_names: list[str],
    output_dir: Path,
    minio_client: Any,
    bucket: str,
    splits: dict[str, str] | None = None,
) -> Path:
    """Export a classification dataset as ImageFolder (``<split>/<class>/img``).

    Returns the dataset *root* directory (containing ``train`` and ``val``).
    """
    splits = splits or {}
    for split in ("train", "val"):
        for cls in class_names:
            (output_dir / split / cls).mkdir(parents=True, exist_ok=True)

    for asset in assets:
        split = splits.get(asset.id, "train")
        if split == "test":
            continue
        if split not in ("train", "val"):
            split = "train"
        ext = Path(asset.uri).suffix or ".jpg"
        img_name = f"{asset.id}{ext}"
        ann_list = annotations_by_asset.get(asset.id, [])
        cls_name = (
            ann_list[0].class_name
            if ann_list and ann_list[0].class_name
            else (class_names[0] if class_names else "unknown")
        )
        dest_dir = output_dir / split / cls_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        img_data = fetch_image_bytes(minio_client, bucket, asset)
        (dest_dir / img_name).write_bytes(img_data or b"")

    return output_dir


def build_yolo_detect(
    assets: list[Any],
    annotations_by_asset: dict[str, list[Any]],
    class_names: list[str],
    output_dir: Path,
    minio_client: Any,
    bucket: str,
    splits: dict[str, str] | None = None,
) -> Path:
    """Export a detection dataset in YOLO format. Returns the ``data.yaml`` path."""
    splits = splits or {}
    images_train = output_dir / "train" / "images"
    images_val = output_dir / "val" / "images"
    labels_train = output_dir / "train" / "labels"
    labels_val = output_dir / "val" / "labels"
    for d in (images_train, images_val, labels_train, labels_val):
        d.mkdir(parents=True, exist_ok=True)

    class_idx: dict[str, int] = {name: i for i, name in enumerate(class_names)}

    for asset in assets:
        split = splits.get(asset.id, "train")
        if split == "test":
            continue
        if split not in ("train", "val"):
            split = "train"
        ext = Path(asset.uri).suffix or ".jpg"
        img_name = f"{asset.id}{ext}"
        img_data = fetch_image_bytes(minio_client, bucket, asset)

        dest_img = (images_train if split == "train" else images_val) / img_name
        dest_img.write_bytes(img_data or b"")

        label_dir = labels_train if split == "train" else labels_val
        label_file = label_dir / f"{asset.id}.txt"
        lines: list[str] = []
        for ann in annotations_by_asset.get(asset.id, []):
            try:
                geo = json.loads(ann.geometry) if isinstance(ann.geometry, str) else ann.geometry
            except Exception:
                continue
            if not isinstance(geo, dict):
                continue
            idx = class_idx.get(ann.class_name or "", 0)
            w_img = asset.width or 640
            h_img = asset.height or 640
            if "x1" in geo:
                bx = (geo["x1"] + geo["x2"]) / 2 / w_img
                by = (geo["y1"] + geo["y2"]) / 2 / h_img
                bw = (geo["x2"] - geo["x1"]) / w_img
                bh = (geo["y2"] - geo["y1"]) / h_img
            else:
                bx = (geo.get("x", 0) + geo.get("w", 0) / 2) / w_img
                by = (geo.get("y", 0) + geo.get("h", 0) / 2) / h_img
                bw = geo.get("w", 0) / w_img
                bh = geo.get("h", 0) / h_img
            lines.append(f"{idx} {bx:.6f} {by:.6f} {bw:.6f} {bh:.6f}")
        label_file.write_text("\n".join(lines))

    data_yaml = output_dir / "data.yaml"
    data_yaml.write_text(
        f"path: {output_dir}\n"
        f"train: train/images\n"
        f"val: val/images\n"
        f"nc: {len(class_names)}\n"
        f"names: {json.dumps(class_names)}\n"
    )
    return data_yaml
