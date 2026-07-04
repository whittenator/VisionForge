"""Per-workspace object-storage backend strategy layer.

VisionForge stores blobs in an S3-compatible object store. Each workspace may
pick one of two backends:

* ``"minio"`` — uses the ``minio.Minio`` client (the platform default). With no
  per-workspace configuration it falls back to the ``MINIO_*`` environment
  defaults via :func:`app.services.storage.get_minio_client`.
* ``"s3"`` — uses ``boto3.client("s3", ...)`` with an endpoint/region/keys taken
  from the workspace's stored configuration.

The public surface is:

* :func:`resolve_workspace_storage` — read a workspace's backend + parsed JSON
  config and return a :class:`StorageSettings` (env-default MinIO when unset).
* :func:`settings_from` — build :class:`StorageSettings` from an explicit
  backend + config dict (used by the settings API for ad-hoc "test" calls).
* :func:`get_client` — return a live client for the given settings.
* :func:`presign_put_url` / :func:`presign_get_url` — backend-aware presigned URLs.
* :func:`test_connection` — a lightweight reachability probe (bucket exists / head).
* :func:`public_config` — a redacted config dict safe to return from the API.

Secret keys are never returned to callers: :func:`public_config` redacts them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from minio import Minio
from sqlalchemy.orm import Session

from app.models.workspace import Workspace

try:  # boto3 is optional at import time; the module must import without it.
    import boto3
except ImportError:  # pragma: no cover - exercised only when boto3 is absent
    boto3 = None  # type: ignore[assignment]


VALID_BACKENDS: tuple[str, ...] = ("minio", "s3")
DEFAULT_BACKEND = "minio"


@dataclass
class StorageSettings:
    """Resolved storage configuration for a single workspace.

    ``secret_key`` is intentionally never surfaced to API callers — use
    :func:`public_config` to build a response-safe view.
    """

    backend: str
    bucket: str
    endpoint: str | None = None
    region: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    secure: bool = False
    # True when this MinIO config came purely from environment defaults (no
    # per-workspace overrides), so ``get_client`` can reuse ``get_minio_client``.
    from_env: bool = False


def _env_default_bucket() -> str:
    return os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))


def settings_from(backend: str | None, cfg: dict[str, Any] | None) -> StorageSettings:
    """Build :class:`StorageSettings` from a backend name and config dict.

    Unknown backends fall back to ``"minio"``. Missing MinIO fields fall back to
    the ``MINIO_*`` environment defaults.
    """
    cfg = cfg or {}
    backend = backend if backend in VALID_BACKENDS else DEFAULT_BACKEND
    env_bucket = _env_default_bucket()

    if backend == "s3":
        return StorageSettings(
            backend="s3",
            bucket=cfg.get("bucket") or env_bucket,
            endpoint=cfg.get("endpoint"),
            region=cfg.get("region"),
            access_key=cfg.get("access_key"),
            secret_key=cfg.get("secret_key"),
            secure=bool(cfg.get("secure", True)),
            from_env=False,
        )

    # minio backend
    has_overrides = any(cfg.get(k) for k in ("endpoint", "access_key", "secret_key", "bucket"))
    env_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    return StorageSettings(
        backend="minio",
        bucket=cfg.get("bucket") or env_bucket,
        endpoint=cfg.get("endpoint") or os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        region=cfg.get("region"),
        access_key=cfg.get("access_key") or os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=cfg.get("secret_key") or os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=bool(cfg.get("secure", env_secure)),
        from_env=not has_overrides,
    )


def resolve_workspace_storage(db: Session, workspace_id: str | None) -> StorageSettings:
    """Resolve the effective storage settings for ``workspace_id``.

    Reads ``Workspace.storage_backend`` and the parsed ``storage_config`` JSON,
    falling back to env-based MinIO defaults when the workspace is missing or has
    no stored configuration.
    """
    ws = db.get(Workspace, workspace_id) if workspace_id else None
    backend = ws.storage_backend if ws and ws.storage_backend else DEFAULT_BACKEND
    cfg: dict[str, Any] = {}
    if ws and ws.storage_config:
        try:
            parsed = json.loads(ws.storage_config)
            if isinstance(parsed, dict):
                cfg = parsed
        except (ValueError, TypeError):
            cfg = {}
    return settings_from(backend, cfg)


def get_client(settings: StorageSettings) -> Any:
    """Return a live object-storage client for ``settings``.

    MinIO returns a ``minio.Minio``; s3 returns a ``boto3`` s3 client.
    """
    if settings.backend == "s3":
        if boto3 is None:
            raise RuntimeError("boto3 is not installed; the 's3' storage backend is unavailable")
        kwargs: dict[str, Any] = {}
        if settings.endpoint:
            kwargs["endpoint_url"] = _normalize_s3_endpoint(settings.endpoint, settings.secure)
        if settings.region:
            kwargs["region_name"] = settings.region
        if settings.access_key:
            kwargs["aws_access_key_id"] = settings.access_key
        if settings.secret_key:
            kwargs["aws_secret_access_key"] = settings.secret_key
        return boto3.client("s3", **kwargs)

    # minio backend
    if settings.from_env:
        from app.services.storage import get_minio_client

        return get_minio_client()
    return Minio(
        settings.endpoint or "localhost:9000",
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        secure=settings.secure,
    )


def _normalize_s3_endpoint(endpoint: str, secure: bool) -> str:
    """Ensure a boto3 ``endpoint_url`` carries a scheme.

    MinIO-style endpoints are bare ``host:port``; boto3 wants a full URL.
    """
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    scheme = "https" if secure else "http"
    return f"{scheme}://{endpoint}"


def presign_put_url(
    settings: StorageSettings,
    object_name: str,
    content_type: str | None = None,
    expires: int = 3600,
) -> str:
    """Return a presigned PUT URL for ``object_name`` in the configured bucket."""
    client = get_client(settings)
    if settings.backend == "s3":
        params: dict[str, Any] = {"Bucket": settings.bucket, "Key": object_name}
        if content_type:
            params["ContentType"] = content_type
        return client.generate_presigned_url("put_object", Params=params, ExpiresIn=expires)
    return client.presigned_put_object(
        settings.bucket, object_name, expires=timedelta(seconds=expires)
    )


def presign_get_url(
    settings: StorageSettings,
    object_name: str,
    expires: int = 3600,
) -> str:
    """Return a presigned GET URL for ``object_name`` in the configured bucket."""
    client = get_client(settings)
    if settings.backend == "s3":
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.bucket, "Key": object_name},
            ExpiresIn=expires,
        )
    return client.presigned_get_object(
        settings.bucket, object_name, expires=timedelta(seconds=expires)
    )


def test_connection(settings: StorageSettings) -> tuple[bool, str]:
    """Lightweight reachability probe: head/list the configured bucket.

    Returns ``(ok, detail)``. A reachable store with a missing bucket still
    counts as a successful connection (the detail notes the bucket state).
    """
    try:
        client = get_client(settings)
        if settings.backend == "s3":
            client.head_bucket(Bucket=settings.bucket)
            return True, f"Connected to s3 endpoint; bucket '{settings.bucket}' is reachable."
        exists = client.bucket_exists(settings.bucket)
        state = "exists" if exists else "does not exist yet"
        return True, f"Connected to MinIO endpoint; bucket '{settings.bucket}' {state}."
    except Exception as exc:  # noqa: BLE001 - surface any failure as a test result
        return False, f"Connection failed: {exc}"


def public_config(settings: StorageSettings) -> dict[str, Any]:
    """Response-safe view of ``settings`` with the secret key redacted.

    ``access_key`` is treated like a username and returned; ``secret_key`` is
    never echoed — only a boolean ``secret_key_set`` flag indicates its presence.
    """
    return {
        "endpoint": settings.endpoint,
        "region": settings.region,
        "bucket": settings.bucket,
        "access_key": settings.access_key,
        "secret_key": None,
        "secret_key_set": bool(settings.secret_key),
        "secure": settings.secure,
    }
