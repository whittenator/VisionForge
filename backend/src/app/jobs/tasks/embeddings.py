from __future__ import annotations

import json
import os
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


@shared_task(name="app.jobs.tasks.embeddings.generate_embeddings")
def generate_embeddings(payload: dict) -> dict:
    job_id = payload.get("jobId")
    dataset_version_id = payload.get("datasetVersionId")
    texts = payload.get("texts") or []
    db = _make_session()
    result: dict = {}

    try:
        from app.models.asset import Asset
        from app.services.embeddings_service import EmbeddingsService
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        svc = EmbeddingsService()
        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_disabled = os.getenv("MINIO_DISABLED", "false").lower() == "true"

        minio_client = None
        if not minio_disabled:
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        # ---- Image embeddings from asset files ----
        image_vectors: list[list[float]] = []
        if dataset_version_id:
            assets = db.query(Asset).filter(Asset.version_id == dataset_version_id).all()
            total = len(assets)

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                for idx, asset in enumerate(assets):
                    try:
                        img_path: str | None = None
                        if minio_client:
                            key = _extract_minio_key(asset.uri)
                            try:
                                response = minio_client.get_object(bucket, key)
                                local_file = tmp_path / f"{asset.id}.bin"
                                local_file.write_bytes(response.read())
                                response.close()
                                response.release_conn()
                                img_path = str(local_file)
                            except Exception:
                                img_path = None

                        if img_path:
                            vec = svc.embed_images([img_path])[0]
                        else:
                            # Fallback: embed using the asset URI as a text key
                            vec = svc._hash_fallback(asset.uri)

                        image_vectors.append(vec)

                        # Persist embedding into Asset.meta_data
                        meta: dict = {}
                        if asset.meta_data:
                            try:
                                meta = json.loads(asset.meta_data)
                            except Exception:
                                meta = {}
                        meta["embedding"] = vec
                        asset.meta_data = json.dumps(meta)
                        db.add(asset)

                        # Commit in batches to avoid long transactions
                        if (idx + 1) % 50 == 0:
                            db.commit()
                            if job_id:
                                progress = 0.1 + 0.8 * ((idx + 1) / max(total, 1))
                                update_job_status(db, job_id, status="running", progress=progress)

                    except Exception:
                        image_vectors.append([])

                db.commit()

        # ---- Text embeddings from explicit texts list ----
        text_vectors: list[list[float]] = []
        if texts:
            text_vectors = svc.embed_texts(texts)

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "image_count": len(image_vectors),
            "text_count": len(text_vectors),
            # For backwards compatibility: return combined vectors
            "count": len(text_vectors) or len(image_vectors),
            "vectors": text_vectors or image_vectors,
        }

    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        try:
            if job_id:
                from app.services.jobs_service import update_job_status
                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
