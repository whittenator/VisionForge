from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap

SYSTEM_USER_ID = os.getenv("SYSTEM_USER_ID", "00000000-0000-0000-0000-000000000001")
CONF_THRESHOLD = 0.5


def _make_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./test.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _extract_minio_key(uri: str) -> str:
    """Extract the object key from an asset URI."""
    for prefix in ("s3://", "minio://"):
        if uri.startswith(prefix):
            parts = uri[len(prefix):].split("/", 1)
            return parts[1] if len(parts) > 1 else uri
    if uri.startswith("http://") or uri.startswith("https://"):
        path = uri.split("/", 3)
        return path[3] if len(path) > 3 else uri
    return uri


@shared_task(name="app.jobs.tasks.prelabels.apply_prelabels")
def apply_prelabels(payload: dict) -> dict:
    job_id = payload.get("jobId")
    dataset_version_id = payload.get("datasetVersionId")
    model_key = payload.get("modelKey")  # MinIO key for .pt model
    task_type = payload.get("task", "detect")  # detect | classify
    conf_threshold: float = float(payload.get("confThreshold", CONF_THRESHOLD))

    db = _make_session()
    result: dict = {}

    try:
        from app.models.annotation import Annotation
        from app.models.asset import Asset
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        # Fetch unlabeled assets for the dataset version
        assets: list[Asset] = []
        if dataset_version_id:
            assets = (
                db.query(Asset)
                .filter(
                    Asset.version_id == dataset_version_id,
                    Asset.label_status == "unlabelled",
                )
                .all()
            )

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_disabled = os.getenv("MINIO_DISABLED", "false").lower() == "true"

        minio_client = None
        if not minio_disabled:
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        labeled_count = 0

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Attempt to load YOLO model from MinIO
            yolo_model = None
            model_names: dict[int, str] = {}
            if model_key and minio_client:
                try:
                    from ultralytics import YOLO  # type: ignore

                    pt_path = tmp_path / "model.pt"
                    response = minio_client.get_object(bucket, model_key)
                    pt_path.write_bytes(response.read())
                    response.close()
                    response.release_conn()
                    yolo_model = YOLO(str(pt_path))
                    model_names = yolo_model.names or {}
                except Exception:
                    yolo_model = None

            total = len(assets)
            for idx, asset in enumerate(assets):
                annotations_created = 0

                if yolo_model is not None and minio_client:
                    try:
                        key = _extract_minio_key(asset.uri)
                        response = minio_client.get_object(bucket, key)
                        img_data = response.read()
                        response.close()
                        response.release_conn()
                        img_path = tmp_path / f"{asset.id}.bin"
                        img_path.write_bytes(img_data)

                        predictions = yolo_model.predict(
                            str(img_path),
                            verbose=False,
                            conf=conf_threshold,
                        )

                        for pred in predictions:
                            if task_type == "classify":
                                # Classification: single label per image
                                probs = getattr(pred, "probs", None)
                                if probs is None:
                                    continue
                                top_conf = float(probs.top1conf) if hasattr(probs, "top1conf") else 0.0
                                if top_conf < conf_threshold:
                                    continue
                                cls_idx = int(probs.top1) if hasattr(probs, "top1") else 0
                                cls_name = model_names.get(cls_idx, str(cls_idx))
                                ann = Annotation(
                                    id=str(uuid.uuid4()),
                                    asset_id=asset.id,
                                    type="classification",
                                    geometry=json.dumps({}),
                                    class_name=cls_name,
                                    author_id=SYSTEM_USER_ID,
                                )
                                db.add(ann)
                                annotations_created += 1

                            else:
                                # Detection: one annotation per box above threshold
                                boxes = getattr(pred, "boxes", None)
                                if boxes is None or len(boxes) == 0:
                                    continue
                                xyxy = boxes.xyxy.tolist() if hasattr(boxes.xyxy, "tolist") else list(boxes.xyxy)
                                confs = boxes.conf.tolist() if hasattr(boxes.conf, "tolist") else list(boxes.conf)
                                clss = boxes.cls.tolist() if hasattr(boxes.cls, "tolist") else list(boxes.cls)

                                for (x1, y1, x2, y2), conf, cls_id in zip(xyxy, confs, clss, strict=False):
                                    if float(conf) < conf_threshold:
                                        continue
                                    cls_name = model_names.get(int(cls_id), str(int(cls_id)))
                                    geo = {
                                        "x": float(x1),
                                        "y": float(y1),
                                        "w": float(x2 - x1),
                                        "h": float(y2 - y1),
                                    }
                                    ann = Annotation(
                                        id=str(uuid.uuid4()),
                                        asset_id=asset.id,
                                        type="box",
                                        geometry=json.dumps(geo),
                                        class_name=cls_name,
                                        author_id=SYSTEM_USER_ID,
                                    )
                                    db.add(ann)
                                    annotations_created += 1

                    except Exception:
                        pass

                # Update label status
                if annotations_created > 0:
                    asset.label_status = "prelabeled"
                    db.add(asset)
                    labeled_count += 1

                # Commit in batches
                if (idx + 1) % 25 == 0:
                    db.commit()
                    if job_id and total > 0:
                        progress = 0.1 + 0.85 * ((idx + 1) / total)
                        update_job_status(db, job_id, status="running", progress=progress)

            db.commit()

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "labeled_count": labeled_count,
            "total_assets": len(assets),
        }

    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "labeled_count": 0}
        try:
            if job_id:
                from app.services.jobs_service import update_job_status
                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
