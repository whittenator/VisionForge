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


@shared_task(name="app.jobs.tasks.frame_extraction.extract_frames")
def extract_frames(payload: dict) -> dict:
    job_id = payload.get("jobId")
    asset_id = payload.get("assetId")
    dataset_version_id = payload.get("datasetVersionId")
    # Extract one frame per `fps_interval` seconds (default: 1 frame/sec)
    fps_interval: float = float(payload.get("fpsInterval", 1.0))

    db = _make_session()
    result: dict = {}

    try:
        from app.models.asset import Asset
        from app.services.jobs_service import update_job_status
        from app.services.storage import ensure_bucket, get_minio_client

        if job_id:
            update_job_status(db, job_id, status="running", progress=0.05)

        # Fetch the video asset
        video_asset: Asset | None = db.get(Asset, asset_id) if asset_id else None
        if video_asset is None:
            raise ValueError(f"Asset {asset_id!r} not found")

        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        minio_disabled = os.getenv("MINIO_DISABLED", "false").lower() == "true"

        minio_client = None
        if not minio_disabled:
            try:
                minio_client = get_minio_client()
                ensure_bucket(minio_client, bucket)
            except Exception:
                minio_client = None

        frame_assets: list[dict] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "video.bin"

            # Download video from MinIO
            if minio_client:
                key = _extract_minio_key(video_asset.uri)
                try:
                    response = minio_client.get_object(bucket, key)
                    video_path.write_bytes(response.read())
                    response.close()
                    response.release_conn()
                except Exception as dl_err:
                    raise RuntimeError(f"Failed to download video from MinIO: {dl_err}") from dl_err
            else:
                raise RuntimeError("MinIO is disabled; cannot download video for frame extraction")

            if job_id:
                update_job_status(db, job_id, status="running", progress=0.2)

            # Use OpenCV to extract frames
            try:
                import cv2  # type: ignore

                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    raise RuntimeError(f"cv2 could not open video: {video_path}")

                video_fps: float = cap.get(cv2.CAP_PROP_FPS) or 25.0
                total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                frame_step: int = max(1, int(round(video_fps * fps_interval)))

                frame_num = 0
                extracted_count = 0

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_num % frame_step == 0:
                        frame_filename = f"frame_{extracted_count:06d}.jpg"
                        local_frame = tmp_path / frame_filename
                        cv2.imwrite(str(local_frame), frame)

                        h, w = frame.shape[:2]
                        minio_key = f"datasets/{dataset_version_id}/frames/{asset_id}/{frame_filename}"

                        if minio_client:
                            try:
                                minio_client.fput_object(bucket, minio_key, str(local_frame))
                            except Exception:
                                pass

                        # Build the asset URI
                        asset_uri = minio_key

                        # Create Asset row for the frame
                        frame_asset = Asset(
                            id=str(uuid.uuid4()),
                            dataset_id=video_asset.dataset_id,
                            version_id=dataset_version_id or video_asset.version_id,
                            uri=asset_uri,
                            mime_type="image/jpeg",
                            width=w,
                            height=h,
                            meta_data=json.dumps({
                                "source_asset_id": asset_id,
                                "frame_number": frame_num,
                                "timestamp_seconds": frame_num / video_fps,
                            }),
                            label_status="unlabelled",
                        )
                        db.add(frame_asset)
                        frame_assets.append({
                            "id": frame_asset.id,
                            "frame_number": frame_num,
                            "key": minio_key,
                        })

                        # Commit in batches
                        if (extracted_count + 1) % 25 == 0:
                            db.commit()
                            if job_id and total_frames > 0:
                                progress = 0.2 + 0.75 * (frame_num / total_frames)
                                update_job_status(db, job_id, status="running", progress=progress)

                        extracted_count += 1

                    frame_num += 1

                cap.release()
                db.commit()

            except ImportError:
                # OpenCV not available — return empty result gracefully
                frame_assets = []

        if job_id:
            update_job_status(db, job_id, status="succeeded", progress=1.0)

        result = {
            "status": "succeeded",
            "frames": frame_assets,
            "frame_count": len(frame_assets),
        }

    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "frames": []}
        try:
            if job_id:
                from app.services.jobs_service import update_job_status
                update_job_status(db, job_id, status="failed", progress=0.0)
        except Exception:
            pass
    finally:
        db.close()

    return result
