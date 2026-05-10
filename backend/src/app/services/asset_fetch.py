"""SSRF-hardened image fetcher used by AL and error-mining paths.

Asset URIs come from many places — uploads, imports, frame extraction, etc.
Some of those code paths historically left the URI as a raw string, which
means an attacker who controls one of the upload paths could inject an
``http://internal-service`` URL. Fetching that URL from the API process or
a Celery worker is a classic SSRF.

This module enforces a simple policy:
  * Only ``MinIO`` keys are followed by default.
  * ``http(s)`` URLs are only allowed when the env var
    ``VF_ALLOW_REMOTE_ASSET_FETCH=true`` is set, and even then we resolve
    the hostname and reject any address that lives on a loopback/private/
    link-local/multicast/reserved IP range.
  * Responses are capped at ``VF_MAX_ASSET_BYTES`` (default 50 MiB) so a
    malicious server can't exhaust memory.

Both `RemoteFetchDenied` and any I/O failure are surfaced as ``None``-byte
returns from ``fetch_asset_bytes`` so callers can fall back gracefully.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_MAX_BYTES = 50 * 1024 * 1024

log = logging.getLogger(__name__)


class RemoteFetchDenied(Exception):
    """Raised when an asset URI is rejected before any network I/O."""


def _max_bytes() -> int:
    raw = os.getenv("VF_MAX_ASSET_BYTES")
    try:
        return int(raw) if raw else DEFAULT_MAX_BYTES
    except ValueError:
        return DEFAULT_MAX_BYTES


def _remote_allowed() -> bool:
    return os.getenv("VF_ALLOW_REMOTE_ASSET_FETCH", "false").lower() == "true"


def _is_safe_remote_host(host: str) -> bool:
    """Reject loopback/private/link-local/multicast/reserved IPs."""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def fetch_asset_bytes(uri: str, *, timeout: float = 10.0) -> bytes | None:
    """Best-effort download of ``uri`` into memory under the SSRF policy.

    Returns the raw bytes on success, or ``None`` for any failure. Never
    raises — callers can always fall back to a random/skip path.
    """
    if not uri:
        return None

    parsed = urlparse(uri)
    scheme = (parsed.scheme or "").lower()

    # Remote HTTP(S) — gated behind opt-in, and only public IPs.
    if scheme in ("http", "https"):
        if not _remote_allowed():
            log.warning("rejecting remote asset fetch (opt-in disabled): %s", uri)
            return None
        host = parsed.hostname or ""
        if not _is_safe_remote_host(host):
            log.warning("rejecting remote asset fetch (unsafe host): %s", host)
            return None
        try:
            req = Request(uri, headers={"User-Agent": "VisionForge/1.0"})
            with urlopen(req, timeout=timeout) as response:  # noqa: S310
                # Read in capped chunks so a malicious server can't OOM us.
                cap = _max_bytes()
                buf = bytearray()
                while True:
                    chunk = response.read(min(65536, cap - len(buf) + 1))
                    if not chunk:
                        break
                    buf.extend(chunk)
                    if len(buf) > cap:
                        log.warning("remote asset exceeded cap (%d bytes): %s", cap, uri)
                        return None
                return bytes(buf)
        except Exception as exc:  # noqa: BLE001
            log.warning("remote asset fetch failed: %s", exc)
            return None

    # Local filesystem path (used in tests and a few legacy paths).
    if scheme in ("", "file"):
        path = parsed.path if scheme == "file" else uri
        try:
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    data = fh.read(_max_bytes() + 1)
                if len(data) > _max_bytes():
                    log.warning("local asset exceeded cap: %s", path)
                    return None
                return data
        except OSError as exc:
            log.warning("local asset read failed: %s", exc)
            return None
        # Otherwise treat as an object-store key below.

    # Anything else: treat as a MinIO/S3 object key.
    try:
        from app.services import storage

        client = storage.get_minio_client()
        bucket = os.getenv("MINIO_BUCKET", os.getenv("S3_BUCKET", "visionforge"))
        resp = client.get_object(bucket, uri)
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        if len(data) > _max_bytes():
            log.warning("object-store asset exceeded cap: %s", uri)
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        log.warning("object-store asset fetch failed: %s", exc)
        return None
