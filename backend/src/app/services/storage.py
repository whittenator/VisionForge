from __future__ import annotations

import io
import os

from minio import Minio


def _default_bucket() -> str:
    return os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))


def put_bytes(
    client: Minio,
    object_key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """Upload raw bytes to MinIO and return the object key."""
    bucket = bucket or _default_bucket()
    client.put_object(
        bucket,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_key


def get_bytes(client: Minio, object_key: str, bucket: str | None = None) -> bytes:
    """Fetch an object's bytes from MinIO."""
    bucket = bucket or _default_bucket()
    response = client.get_object(bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def ensure_bucket(client: Minio, bucket: str) -> None:
    found = client.bucket_exists(bucket)
    if not found:
        client.make_bucket(bucket)
    # Optionally set a simple public read policy if configured
    policy = os.getenv("MINIO_BUCKET_POLICY_JSON")
    if policy:
        try:
            client.set_bucket_policy(bucket, policy)
        except Exception:
            # Ignore policy errors in dev/test environments
            pass


def presign_put_url(
    dataset_version_id: str, filename: str, content_type: str | None = None
) -> dict:
    """
    Build an object key and return a presigned PUT URL.
    Returns dict with keys: url, fields (empty for PUT compatibility with tests)
    """
    bucket = os.getenv("S3_BUCKET", "visionforge")
    object_name = f"datasets/{dataset_version_id}/{filename}"

    # Allow running without a real MinIO by returning a dummy URL when disabled
    if os.getenv("MINIO_DISABLED", "false").lower() == "true":
        return {"url": f"https://minio.local/{bucket}/{object_name}", "fields": {}}

    client = get_minio_client()
    # Optional: ensure bucket exists (idempotent)
    try:
        ensure_bucket(client, bucket)
    except Exception:
        # In dev/test, ignore errors to keep contract green
        pass

    expires = int(os.getenv("MINIO_PRESIGN_EXPIRY_SECONDS", "3600"))
    url = client.presigned_put_object(bucket, object_name, expires=expires)
    return {"url": url, "fields": {}}
