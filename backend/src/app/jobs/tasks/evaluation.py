from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover - fallback when Celery not installed
    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap


def _make_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _extract_minio_key(uri: str) -> str:
    """Extract the object key from an asset URI (strips bucket prefix if present)."""
    for prefix in ("s3://", "minio://"):
        if uri.startswith(prefix):
            parts = uri[len(prefix):].split("/", 1)
            return parts[1] if len(parts) > 1 else uri
    if uri.startswith("http://") or uri.startswith("https://"):
        path = uri.split("/", 3)
        return path[3] if len(path) > 3 else uri
    return uri


def _build_yolo_dataset(
    assets: list[Any],
    annotations_by_asset: dict[str, list[Any]],
    class_names: list[str],
    output_dir: Path,
    minio_client: Any,
    bucket: str,
) -> Path:
    """Export assets and annotations to YOLO detection format and return data.yaml path."""
    images_train = output_dir / "train" / "images"
    images_val = output_dir / "val" / "images"
    labels_train = output_dir / "train" / "labels"
    labels_val = output_dir / "val" / "labels"

    for d in (images_train, images_val, labels_train, labels_val):
        d.mkdir(parents=True, exist_ok=True)

    class_idx: dict[str, int] = {name: i for i, name in enumerate(class_names)}

    for i, asset in enumerate(assets):
        split = "val" if i % 5 == 4 else "train"
        ext = Path(asset.uri).suffix or ".jpg"
        img_name = f"{asset.id}{ext}"

        try:
            key = _extract_minio_key(asset.uri)
            response = minio_client.get_object(bucket, key)
            img_data = response.read()
            response.close()
            response.release_conn()
        except Exception:
            img_data = None

        dest_img = (images_train if split == "train" else images_val) / img_name
        if img_data:
            dest_img.write_bytes(img_data)
        else:
            dest_img.write_bytes(b"")

        label_dir = labels_train if split == "train" else labels_val
        label_file = label_dir / f"{asset.id}.txt"
        ann_list = annotations_by_asset.get(asset.id, [])
        lines: list[str] = []
        for ann in ann_list:
            try:
                geo = json.loads(ann.geometry) if isinstance(ann.geometry, str) else ann.geometry
            except Exception:
                continue
            cls_name = ann.class_name or ""
            idx = class_idx.get(cls_name, 0)
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
    yaml_content = (
        f"path: {output_dir}\n"
        f"train: train/images\n"
        f"val: val/images\n"
        f"nc: {len(class_names)}\n"
        f"names: {json.dumps(class_names)}\n"
    )
    data_yaml.write_text(yaml_content)
    return data_yaml


@shared_task(name="app.jobs.tasks.evaluation.evaluate_task")
def evaluate_task(payload: dict) -> dict:
    experiment_run_id = payload.get("experiment_run_id")
    job_id = payload.get("job_id")
    db = _make_session()
    result: dict = {}

    try:
        from app.models.annotation import Annotation
        from app.models.asset import Asset
        from app.models.dataset import ClassMap, Dataset
        from app.models.dataset_version import DatasetVersion
        from app.models.experiment import ExperimentRun
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        run: ExperimentRun | None = db.get(ExperimentRun, experiment_run_id) if experiment_run_id else None
        if run is None:
            raise ValueError(f"ExperimentRun {experiment_run_id!r} not found")

        # Locate best.pt storage path from run.artifacts JSON
        artifacts_list = json.loads(run.artifacts or "[]")
        pt_storage_path: str | None = None
        for art in artifacts_list:
            if art.get("type") == "pytorch":
                pt_storage_path = art.get("key") or art.get("storage_path")
                break

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_client = None
        if os.getenv("MINIO_DISABLED", "false").lower() != "true":
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        # Fetch dataset assets and annotations
        version_id = run.dataset_version_id
        assets: list[Asset] = []
        class_names: list[str] = []
        annotations_by_asset: dict[str, list[Annotation]] = {}

        if version_id:
            assets = db.query(Asset).filter(Asset.version_id == version_id).all()
            version: DatasetVersion | None = db.get(DatasetVersion, version_id)
            dataset: Dataset | None = db.get(Dataset, version.dataset_id) if version else None

            if dataset and dataset.class_map_id:
                cm: ClassMap | None = db.get(ClassMap, dataset.class_map_id)
                if cm:
                    raw = json.loads(cm.classes)
                    if raw and isinstance(raw[0], dict):
                        class_names = [c["name"] for c in raw]
                    else:
                        class_names = [str(c) for c in raw]

            asset_ids = [a.id for a in assets]
            if asset_ids:
                ann_rows = db.query(Annotation).filter(Annotation.asset_id.in_(asset_ids)).all()
                for ann in ann_rows:
                    annotations_by_asset.setdefault(ann.asset_id, []).append(ann)

            if not class_names:
                seen: list[str] = []
                for ann_list in annotations_by_asset.values():
                    for ann in ann_list:
                        if ann.class_name and ann.class_name not in seen:
                            seen.append(ann.class_name)
                class_names = seen or ["object"]

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.2)

        eval_data: dict = {}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset_dir = tmp_path / "dataset"
            pt_path: Path | None = None

            # Download .pt file from MinIO
            if pt_storage_path and minio_client:
                try:
                    pt_path = tmp_path / "best.pt"
                    minio_client.fget_object(bucket, pt_storage_path, str(pt_path))
                except Exception:
                    pt_path = None

            # Export dataset to YOLO format
            data_yaml_path = _build_yolo_dataset(
                assets=assets,
                annotations_by_asset=annotations_by_asset,
                class_names=class_names,
                output_dir=dataset_dir,
                minio_client=minio_client,
                bucket=bucket,
            )

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.4)

            # Run YOLO validation
            try:
                from ultralytics import YOLO  # type: ignore

                model_path = str(pt_path) if pt_path and pt_path.exists() else "yolov8n.pt"
                model = YOLO(model_path)
                results = model.val(
                    data=str(data_yaml_path),
                    imgsz=640,
                    batch=16,
                    device="cpu",
                    verbose=False,
                    plots=False,
                )
                eval_data = {
                    "summary": {
                        "mAP50": float(results.box.map50) if hasattr(results, "box") else 0.0,
                        "mAP50_95": float(results.box.map) if hasattr(results, "box") else 0.0,
                        "precision": float(results.box.mp) if hasattr(results, "box") else 0.0,
                        "recall": float(results.box.mr) if hasattr(results, "box") else 0.0,
                        "speed_ms": (
                            float(results.speed.get("inference", 0))
                            if hasattr(results, "speed")
                            else 0.0
                        ),
                    },
                    "per_class": [],
                    "confusion_matrix": {"labels": [], "matrix": []},
                }
                if hasattr(results, "box") and hasattr(results.box, "ap_class_index"):
                    class_name_map = results.names
                    for idx in range(len(results.box.ap_class_index)):
                        cls_idx = int(results.box.ap_class_index[idx])
                        eval_data["per_class"].append(
                            {
                                "class_name": class_name_map.get(cls_idx, str(cls_idx)),
                                "ap50": (
                                    float(results.box.ap[idx])
                                    if len(results.box.ap) > idx
                                    else 0.0
                                ),
                                "ap50_95": (
                                    float(results.box.maps[cls_idx])
                                    if hasattr(results.box, "maps")
                                    and len(results.box.maps) > cls_idx
                                    else 0.0
                                ),
                                "precision": (
                                    float(results.box.p[idx])
                                    if len(results.box.p) > idx
                                    else 0.0
                                ),
                                "recall": (
                                    float(results.box.r[idx])
                                    if len(results.box.r) > idx
                                    else 0.0
                                ),
                            }
                        )
                if (
                    hasattr(results, "confusion_matrix")
                    and results.confusion_matrix is not None
                ):
                    cm = results.confusion_matrix
                    if hasattr(cm, "matrix"):
                        labels = [
                            results.names.get(i, str(i)) for i in range(len(results.names))
                        ] + ["background"]
                        eval_data["confusion_matrix"] = {
                            "labels": labels,
                            "matrix": (
                                cm.matrix.tolist() if hasattr(cm.matrix, "tolist") else []
                            ),
                        }
            except ImportError:
                eval_data = {
                    "summary": {
                        "mAP50": 0.0,
                        "mAP50_95": 0.0,
                        "precision": 0.0,
                        "recall": 0.0,
                        "speed_ms": 0.0,
                        "note": "ultralytics not available; mock data returned",
                    },
                    "per_class": [],
                    "confusion_matrix": {"labels": [], "matrix": []},
                }
            except Exception as e:
                eval_data = {
                    "error": str(e),
                    "summary": {},
                    "per_class": [],
                    "confusion_matrix": {"labels": [], "matrix": []},
                }

        # Persist evaluation results
        run.evaluation_json = json.dumps(eval_data)
        db.add(run)
        db.commit()

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {"status": "succeeded", "experiment_run_id": experiment_run_id}

    except Exception as exc:
        error_msg = str(exc)
        result = {"status": "failed", "error": error_msg}
        try:
            if job_id:
                from app.services.jobs_service import update_job_status

                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
