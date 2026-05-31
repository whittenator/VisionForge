"""Unit tests for the object-storage abstraction (``services/storage``).

The real MinIO client is replaced with a tiny in-memory fake so we can verify
the bucket/object plumbing, the presign fallback when storage is disabled, and
the ``MINIO_BUCKET`` / ``S3_BUCKET`` precedence — none of which were covered.
"""

from __future__ import annotations

from app.services import storage


class _FakeMinio:
    def __init__(self, existing_buckets=None):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.buckets: set[str] = set(existing_buckets or [])
        self.made_buckets: list[str] = []

    def put_object(self, bucket, key, data, length=None, content_type=None):
        self.objects[(bucket, key)] = data.read()

    def get_object(self, bucket, key):
        payload = self.objects[(bucket, key)]
        return _FakeResponse(payload)

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)
        self.made_buckets.append(bucket)


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload
        self.closed = False
        self.released = False

    def read(self):
        return self._payload

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


def test_default_bucket_prefers_minio_bucket(monkeypatch):
    monkeypatch.setenv("MINIO_BUCKET", "primary")
    monkeypatch.setenv("S3_BUCKET", "secondary")
    assert storage._default_bucket() == "primary"

    monkeypatch.delenv("MINIO_BUCKET", raising=False)
    assert storage._default_bucket() == "secondary"


def test_put_and_get_bytes_round_trip():
    client = _FakeMinio()
    key = storage.put_bytes(client, "a/b.bin", b"hello", bucket="bkt")
    assert key == "a/b.bin"
    assert storage.get_bytes(client, "a/b.bin", bucket="bkt") == b"hello"


def test_get_bytes_closes_and_releases_response():
    client = _FakeMinio()
    storage.put_bytes(client, "k", b"x", bucket="bkt")
    # Patch get_object to hand back a response we can inspect afterwards.
    resp = _FakeResponse(b"x")
    client.get_object = lambda b, k: resp  # type: ignore[assignment]
    assert storage.get_bytes(client, "k", bucket="bkt") == b"x"
    assert resp.closed and resp.released


def test_ensure_bucket_creates_only_when_missing(monkeypatch):
    monkeypatch.delenv("MINIO_BUCKET_POLICY_JSON", raising=False)
    client = _FakeMinio(existing_buckets={"exists"})

    storage.ensure_bucket(client, "exists")
    assert client.made_buckets == []

    storage.ensure_bucket(client, "fresh")
    assert client.made_buckets == ["fresh"]


def test_presign_put_url_disabled_returns_stub(monkeypatch):
    monkeypatch.setenv("MINIO_DISABLED", "true")
    monkeypatch.setenv("S3_BUCKET", "visionforge")
    out = storage.presign_put_url("ver-1", "img.jpg")
    assert out["fields"] == {}
    assert out["url"].endswith("visionforge/datasets/ver-1/img.jpg")


def test_get_minio_client_reads_env(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "storage.local:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "secret")
    monkeypatch.setenv("MINIO_SECURE", "false")
    client = storage.get_minio_client()
    # Constructing the client must not touch the network; just confirm we got a
    # real Minio instance configured from the env vars above.
    from minio import Minio

    assert isinstance(client, Minio)
