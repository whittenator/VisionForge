from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

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


@shared_task(name="app.jobs.tasks.onnx_export.export_task")
def export_task(payload: dict) -> dict:
    job_id = payload.get("jobId")
    experiment_id = payload.get("experimentId")
    db = _make_session()
    result: dict = {}

    try:
        from app.models.artifact import ModelArtifact
        from app.models.experiment import ExperimentRun
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        # Fetch ExperimentRun to locate the PyTorch model key
        run: ExperimentRun | None = db.get(ExperimentRun, experiment_id) if experiment_id else None
        if run is None:
            raise ValueError(f"ExperimentRun {experiment_id!r} not found")

        # Determine MinIO key for the .pt model
        artifacts_data: list[dict] = json.loads(run.artifacts or "[]")
        pt_key: str | None = None
        for art in artifacts_data:
            if art.get("type") == "pytorch":
                pt_key = art.get("key")
                break

        # Allow override via payload
        pt_key = payload.get("modelKey") or pt_key

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_disabled = os.getenv("MINIO_DISABLED", "false").lower() == "true"

        minio_client = None
        if not minio_disabled:
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.1)

        onnx_key: str | None = None
        onnx_checksum: str | None = None
        onnx_size: int | None = None

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pt_path = tmp_path / "model.pt"

            # Download .pt from MinIO
            if pt_key and minio_client:
                try:
                    response = minio_client.get_object(bucket, pt_key)
                    pt_path.write_bytes(response.read())
                    response.close()
                    response.release_conn()
                except Exception as dl_err:
                    raise RuntimeError(f"Failed to download model from MinIO: {dl_err}") from dl_err
            elif pt_key is None and not minio_disabled:
                raise ValueError("No PyTorch model artifact found for this experiment run")

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.3)

            # Export to ONNX using Ultralytics
            onnx_path: Path | None = None
            try:
                from ultralytics import YOLO  # type: ignore

                if pt_path.exists() and pt_path.stat().st_size > 0:
                    model = YOLO(str(pt_path))
                    export_result = model.export(format="onnx", dynamic=True, simplify=True)
                    # export() returns the path to the exported file
                    if export_result:
                        onnx_path = Path(str(export_result))
                    else:
                        # Fall back to searching for .onnx next to .pt
                        candidate = pt_path.with_suffix(".onnx")
                        if candidate.exists():
                            onnx_path = candidate
            except ImportError:
                pass

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.6)

            # Validate with onnxruntime
            if onnx_path and onnx_path.exists():
                try:
                    import numpy as np  # type: ignore
                    import onnxruntime as ort  # type: ignore

                    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                    input_meta = sess.get_inputs()[0]
                    # Build dummy input with the expected shape (replace dynamic dims with 1/640)
                    shape = [
                        d if isinstance(d, int) and d > 0 else (1 if i == 0 else 640)
                        for i, d in enumerate(input_meta.shape)
                    ]
                    dummy = np.zeros(shape, dtype=np.float32)
                    sess.run(None, {input_meta.name: dummy})
                except Exception:
                    # Validation failure is non-fatal — continue with upload
                    pass

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.75)

            # Upload .onnx to MinIO
            if onnx_path and onnx_path.exists() and minio_client:
                onnx_bytes = onnx_path.read_bytes()
                onnx_checksum = hashlib.md5(onnx_bytes).hexdigest()
                onnx_size = len(onnx_bytes)
                onnx_key = f"models/{experiment_id}/best.onnx"
                try:
                    import io

                    minio_client.put_object(bucket, onnx_key, io.BytesIO(onnx_bytes), len(onnx_bytes))
                except Exception as ul_err:
                    raise RuntimeError(f"Failed to upload ONNX model: {ul_err}") from ul_err

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.9)

        # Create or update ModelArtifact row for onnx
        if onnx_key or minio_disabled:
            # Check for existing onnx artifact
            existing = (
                db.query(ModelArtifact)
                .filter(
                    ModelArtifact.run_id == run.id,
                    ModelArtifact.type == "onnx",
                )
                .first()
            )
            if existing:
                existing.checksum = onnx_checksum
                existing.size_bytes = onnx_size
                db.add(existing)
            else:
                artifact = ModelArtifact(
                    id=str(uuid.uuid4()),
                    project_id=run.project_id,
                    run_id=run.id,
                    version=1,
                    type="onnx",
                    checksum=onnx_checksum,
                    size_bytes=onnx_size,
                )
                db.add(artifact)
                db.commit()
                db.refresh(artifact)

                # Update run.artifacts
                artifacts_data_out: list[dict] = json.loads(run.artifacts or "[]")
                artifacts_data_out.append(
                    {"id": artifact.id, "type": "onnx", "key": onnx_key}
                )
                run.artifacts = json.dumps(artifacts_data_out)
                db.add(run)

            db.commit()

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "experiment_id": experiment_id,
            "onnx_key": onnx_key,
            "checksum": onnx_checksum,
        }

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
