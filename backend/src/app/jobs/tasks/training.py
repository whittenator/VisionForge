from __future__ import annotations

import json
import os
import tempfile
import uuid
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
    # URI may be: s3://bucket/key, minio://bucket/key, http://host/bucket/key, or plain key
    for prefix in ("s3://", "minio://"):
        if uri.startswith(prefix):
            parts = uri[len(prefix):].split("/", 1)
            return parts[1] if len(parts) > 1 else uri
    if uri.startswith("http://") or uri.startswith("https://"):
        # http://host/bucket/key  →  key is everything after second /
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
    task_type: str = "detect",
) -> Path:
    """Export assets and annotations to YOLO dataset format and return path to data.yaml."""
    images_train = output_dir / "train" / "images"
    images_val = output_dir / "val" / "images"
    labels_train = output_dir / "train" / "labels"
    labels_val = output_dir / "val" / "labels"

    if task_type == "classify":
        for split in ("train", "val"):
            for cls in class_names:
                (output_dir / split / cls).mkdir(parents=True, exist_ok=True)
    else:
        for d in (images_train, images_val, labels_train, labels_val):
            d.mkdir(parents=True, exist_ok=True)

    class_idx: dict[str, int] = {name: i for i, name in enumerate(class_names)}

    for i, asset in enumerate(assets):
        split = "val" if i % 5 == 4 else "train"
        ext = Path(asset.uri).suffix or ".jpg"
        img_name = f"{asset.id}{ext}"

        # Download image from MinIO
        try:
            key = _extract_minio_key(asset.uri)
            response = minio_client.get_object(bucket, key)
            img_data = response.read()
            response.close()
            response.release_conn()
        except Exception:
            img_data = None

        if task_type == "classify":
            # Determine class from annotations
            ann_list = annotations_by_asset.get(asset.id, [])
            cls_name = ann_list[0].class_name if ann_list else (class_names[0] if class_names else "unknown")
            dest_dir = output_dir / split / cls_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_img = dest_dir / img_name
            if img_data:
                dest_img.write_bytes(img_data)
            else:
                dest_img.write_bytes(b"")
        else:
            dest_img = (images_train if split == "train" else images_val) / img_name
            if img_data:
                dest_img.write_bytes(img_data)
            else:
                dest_img.write_bytes(b"")

            # Write label file
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
                # Support both {x,y,w,h} and {x1,y1,x2,y2} geometry formats
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

    # Write data.yaml
    if task_type == "classify":
        data_yaml = output_dir / "data.yaml"
        yaml_content = (
            f"path: {output_dir}\n"
            f"train: train\n"
            f"val: val\n"
            f"nc: {len(class_names)}\n"
            f"names: {json.dumps(class_names)}\n"
        )
    else:
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


@shared_task(name="app.jobs.tasks.training.train_task")
def train_task(payload: dict) -> dict:
    job_id = payload.get("jobId")
    experiment_id = payload.get("experimentId")
    db = _make_session()
    error_msg: str | None = None
    result: dict = {}

    try:
        from app.models.annotation import Annotation
        from app.models.artifact import ModelArtifact
        from app.models.asset import Asset
        from app.models.dataset import ClassMap, Dataset
        from app.models.dataset_version import DatasetVersion
        from app.models.experiment import ExperimentRun
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        # Mark job running
        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        # Fetch ExperimentRun
        run: ExperimentRun | None = db.get(ExperimentRun, experiment_id) if experiment_id else None
        if run is None:
            raise ValueError(f"ExperimentRun {experiment_id!r} not found")

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()

        params: dict = json.loads(run.params_json or "{}") if run.params_json else {}
        base_model = params.get("base_model", "yolov8n.pt")
        task_type = params.get("task", "detect")  # detect | classify | segment

        # Fetch DatasetVersion and related assets/annotations
        version_id = run.dataset_version_id
        assets: list[Asset] = []
        class_names: list[str] = []
        annotations_by_asset: dict[str, list[Annotation]] = {}

        if version_id:
            assets = db.query(Asset).filter(Asset.version_id == version_id).all()
            version: DatasetVersion | None = db.get(DatasetVersion, version_id)
            dataset: Dataset | None = db.get(Dataset, version.dataset_id) if version else None

            # Build class list from ClassMap
            if dataset and dataset.class_map_id:
                cm: ClassMap | None = db.get(ClassMap, dataset.class_map_id)
                if cm:
                    raw = json.loads(cm.classes)
                    if raw and isinstance(raw[0], dict):
                        class_names = [c["name"] for c in raw]
                    else:
                        class_names = [str(c) for c in raw]

            # Fetch all annotations for these assets
            asset_ids = [a.id for a in assets]
            if asset_ids:
                ann_rows = (
                    db.query(Annotation).filter(Annotation.asset_id.in_(asset_ids)).all()
                )
                for ann in ann_rows:
                    annotations_by_asset.setdefault(ann.asset_id, []).append(ann)

            # If no ClassMap, derive class names from annotations
            if not class_names:
                seen: list[str] = []
                for ann_list in annotations_by_asset.values():
                    for ann in ann_list:
                        if ann.class_name and ann.class_name not in seen:
                            seen.append(ann.class_name)
                class_names = seen or ["object"]

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.1)

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_client = None
        if os.getenv("MINIO_DISABLED", "false").lower() != "true":
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        epoch_metrics: list[dict] = []
        best_pt_path: Path | None = None

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset_dir = tmp_path / "dataset"
            output_dir = tmp_path / "output"
            output_dir.mkdir(parents=True)

            # Export dataset to YOLO format
            data_yaml = _build_yolo_dataset(
                assets=assets,
                annotations_by_asset=annotations_by_asset,
                class_names=class_names,
                output_dir=dataset_dir,
                minio_client=minio_client,
                bucket=bucket,
                task_type=task_type,
            )

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.2)

            # Run YOLO training
            try:
                from ultralytics import YOLO  # type: ignore

                model = YOLO(base_model)
                total_epochs = params.get("epochs", 50)

                def on_train_epoch_end(trainer: Any) -> None:  # noqa: ANN001
                    epoch_num = getattr(trainer, "epoch", 0)
                    metrics_dict = {}
                    if hasattr(trainer, "metrics"):
                        raw_metrics = trainer.metrics
                        if hasattr(raw_metrics, "results_dict"):
                            metrics_dict = dict(raw_metrics.results_dict)
                        elif isinstance(raw_metrics, dict):
                            metrics_dict = raw_metrics
                    if hasattr(trainer, "loss"):
                        loss_val = trainer.loss
                        metrics_dict["loss"] = float(loss_val) if loss_val is not None else None
                    entry = {"epoch": epoch_num, **metrics_dict}
                    epoch_metrics.append(entry)

                    # Persist metrics to DB
                    try:
                        run.metrics_json = json.dumps({"epochs": epoch_metrics})
                        db.add(run)
                        db.commit()
                    except Exception:
                        pass

                    # Update job progress
                    progress = 0.2 + 0.75 * (epoch_num / max(total_epochs, 1))
                    try:
                        if job_id:
                            update_job_status(db, job_id, status="running", progress=progress)
                    except Exception:
                        pass

                model.add_callback("on_train_epoch_end", on_train_epoch_end)

                train_kwargs: dict = {
                    "data": str(data_yaml),
                    "epochs": total_epochs,
                    "imgsz": params.get("imgsz", 640),
                    "batch": params.get("batch", 16),
                    "device": params.get("device", "cpu"),
                    "project": str(output_dir),
                    "name": "train",
                    # Learning rate hyperparameters
                    "lr0": params.get("lr0", 0.01),
                    "lrf": params.get("lrf", 0.01),
                    "momentum": params.get("momentum", 0.937),
                    "weight_decay": params.get("weight_decay", 0.0005),
                    "warmup_epochs": params.get("warmup_epochs", 3.0),
                    # Augmentation parameters
                    "hsv_h": params.get("hsv_h", 0.015),
                    "hsv_s": params.get("hsv_s", 0.7),
                    "hsv_v": params.get("hsv_v", 0.4),
                    "degrees": params.get("degrees", 0.0),
                    "translate": params.get("translate", 0.1),
                    "scale": params.get("scale", 0.5),
                    "shear": params.get("shear", 0.0),
                    "perspective": params.get("perspective", 0.0),
                    "flipud": params.get("flipud", 0.0),
                    "fliplr": params.get("fliplr", 0.5),
                    "mosaic": params.get("mosaic", 1.0),
                    "mixup": params.get("mixup", 0.0),
                    "copy_paste": params.get("copy_paste", 0.0),
                }
                model.train(**train_kwargs)

                # Locate best.pt
                candidate = output_dir / "train" / "weights" / "best.pt"
                if candidate.exists():
                    best_pt_path = candidate
                else:
                    # Fallback: search for any .pt file
                    pt_files = list(output_dir.rglob("*.pt"))
                    best_pt_path = pt_files[0] if pt_files else None

            except ImportError:
                # Ultralytics not installed — record that training was skipped
                epoch_metrics = [{"epoch": 0, "note": "ultralytics not available"}]
                run.metrics_json = json.dumps({"epochs": epoch_metrics})
                db.add(run)
                db.commit()

            # Upload best.pt to MinIO and create ModelArtifact
            minio_key: str | None = None
            if best_pt_path and minio_client:
                try:
                    minio_key = f"models/{experiment_id}/best.pt"
                    minio_client.fput_object(bucket, minio_key, str(best_pt_path))

                    size_bytes = best_pt_path.stat().st_size
                    import hashlib

                    checksum = hashlib.md5(best_pt_path.read_bytes()).hexdigest()

                    artifact = ModelArtifact(
                        id=str(uuid.uuid4()),
                        project_id=run.project_id,
                        run_id=run.id,
                        version=1,
                        type="pytorch",
                        checksum=checksum,
                        size_bytes=size_bytes,
                    )
                    # Store storage_path in checksum field if no dedicated column exists
                    # (ModelArtifact has no storage_path column per the model definition)
                    db.add(artifact)
                    db.commit()
                    db.refresh(artifact)

                    # Record artifact reference in ExperimentRun.artifacts JSON
                    artifacts_data = json.loads(run.artifacts or "[]")
                    artifacts_data.append({"id": artifact.id, "type": "pytorch", "key": minio_key})
                    run.artifacts = json.dumps(artifacts_data)
                    db.add(run)
                    db.commit()
                except Exception as upload_err:
                    # Log but don't fail the task
                    epoch_metrics.append({"warning": f"model upload failed: {upload_err}"})

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.97)

        # Mark experiment run as succeeded
        run.status = "succeeded"
        run.completed_at = datetime.now(timezone.utc)
        if not run.metrics_json:
            run.metrics_json = json.dumps({"epochs": epoch_metrics})
        db.add(run)
        db.commit()

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "experiment_id": experiment_id,
            "epochs_completed": len(epoch_metrics),
            "model_key": minio_key,
        }

    except Exception as exc:
        error_msg = str(exc)
        result = {"status": "failed", "error": error_msg}
        try:
            if experiment_id:
                run_obj = db.get(ExperimentRun, experiment_id) if "ExperimentRun" in dir() else None
                if run_obj:
                    run_obj.status = "failed"
                    run_obj.completed_at = datetime.now(timezone.utc)
                    run_obj.metrics_json = json.dumps({"error": error_msg})
                    db.add(run_obj)
                    db.commit()
        except Exception:
            pass
        try:
            if job_id:
                from app.services.jobs_service import update_job_status
                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
