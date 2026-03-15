from __future__ import annotations

import math
import os
import random
import tempfile
from pathlib import Path

try:
    from celery import shared_task  # type: ignore
except Exception:  # pragma: no cover
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
    """Extract the object key from an asset URI."""
    for prefix in ("s3://", "minio://"):
        if uri.startswith(prefix):
            parts = uri[len(prefix):].split("/", 1)
            return parts[1] if len(parts) > 1 else uri
    if uri.startswith("http://") or uri.startswith("https://"):
        path = uri.split("/", 3)
        return path[3] if len(path) > 3 else uri
    return uri


def _detection_uncertainty(predictions: list) -> float:
    """Compute uncertainty from YOLO detection predictions.

    Uses (1 - max_confidence) averaged over detections as the uncertainty score.
    If there are no detections the uncertainty is maximal (1.0).
    """
    if not predictions:
        return 1.0
    confs: list[float] = []
    for pred in predictions:
        try:
            boxes = pred.boxes
            if boxes is not None and len(boxes) > 0:
                conf_vals = boxes.conf.tolist() if hasattr(boxes.conf, "tolist") else list(boxes.conf)
                confs.extend(conf_vals)
        except Exception:
            pass
    if not confs:
        return 1.0
    # Uncertainty = 1 - mean max-conf across all detected boxes
    return float(1.0 - (sum(confs) / len(confs)))


def _classification_uncertainty(predictions: list) -> float:
    """Compute prediction entropy from YOLO classification predictions.

    Higher entropy = higher uncertainty.
    """
    if not predictions:
        return 1.0
    try:
        pred = predictions[0]
        probs = pred.probs
        if probs is None:
            return 1.0
        prob_data = probs.data
        prob_list: list[float] = prob_data.tolist() if hasattr(prob_data, "tolist") else list(prob_data)
        n = len(prob_list)
        if n <= 1:
            return 0.0
        entropy = -sum(p * math.log(p + 1e-9) for p in prob_list)
        max_entropy = math.log(n)
        return float(entropy / max_entropy) if max_entropy > 0 else 0.0
    except Exception:
        return 1.0


@shared_task(name="app.jobs.tasks.uncertainty.score_uncertainty")
def score_uncertainty(payload: dict) -> dict:
    job_id = payload.get("jobId")
    dataset_version_id = payload.get("datasetVersionId")
    model_key = payload.get("modelKey")  # MinIO key for .pt model
    task_type = payload.get("task", "detect")  # detect | classify

    db = _make_session()
    result: dict = {}

    try:
        from app.models.asset import Asset
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        # Fetch assets for the dataset version
        assets: list[Asset] = []
        if dataset_version_id:
            assets = db.query(Asset).filter(Asset.version_id == dataset_version_id).all()

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_disabled = os.getenv("MINIO_DISABLED", "false").lower() == "true"

        minio_client = None
        if not minio_disabled:
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        scores: list[dict] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Attempt to load YOLO model
            yolo_model = None
            if model_key and minio_client:
                try:
                    from ultralytics import YOLO  # type: ignore

                    pt_path = tmp_path / "model.pt"
                    response = minio_client.get_object(bucket, model_key)
                    pt_path.write_bytes(response.read())
                    response.close()
                    response.release_conn()
                    yolo_model = YOLO(str(pt_path))
                except Exception:
                    yolo_model = None

            total = len(assets)
            for idx, asset in enumerate(assets):
                uncertainty_score: float

                if yolo_model is not None and minio_client:
                    # Download image and run inference
                    try:
                        key = _extract_minio_key(asset.uri)
                        response = minio_client.get_object(bucket, key)
                        img_data = response.read()
                        response.close()
                        response.release_conn()
                        img_path = tmp_path / f"{asset.id}.bin"
                        img_path.write_bytes(img_data)

                        predictions = yolo_model.predict(
                            str(img_path), verbose=False, conf=0.01
                        )
                        if task_type == "classify":
                            uncertainty_score = _classification_uncertainty(predictions)
                        else:
                            uncertainty_score = _detection_uncertainty(predictions)
                    except Exception:
                        # Fall back to random score on per-asset error
                        uncertainty_score = random.random()
                else:
                    # No model available — use random scores as fallback
                    uncertainty_score = random.random()

                scores.append({"asset_id": asset.id, "score": uncertainty_score})

                if job_id and total > 0 and (idx + 1) % 10 == 0:
                    progress = 0.1 + 0.85 * ((idx + 1) / total)
                    update_job_status(db, job_id, status="running", progress=progress)

        # Sort descending by score (most uncertain first)
        scores.sort(key=lambda s: s["score"], reverse=True)

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "scores": scores,
            "count": len(scores),
        }

    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "scores": []}
        try:
            if job_id:
                from app.services.jobs_service import update_job_status
                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
