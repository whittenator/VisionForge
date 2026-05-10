"""Tests for the SSRF policy enforced by services/asset_fetch.py."""

from __future__ import annotations

import os
import socket
from unittest import mock

from app.services import asset_fetch


def test_remote_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VF_ALLOW_REMOTE_ASSET_FETCH", raising=False)
    # Even a public-looking URL is rejected when the opt-in flag is unset.
    assert asset_fetch.fetch_asset_bytes("https://example.com/foo.jpg") is None


def test_remote_enabled_blocks_loopback(monkeypatch):
    monkeypatch.setenv("VF_ALLOW_REMOTE_ASSET_FETCH", "true")
    # Pretend the host resolves to localhost.
    with mock.patch.object(
        asset_fetch.socket,
        "getaddrinfo",
        return_value=[(socket.AF_INET, None, None, "", ("127.0.0.1", 0))],
    ):
        assert asset_fetch.fetch_asset_bytes("http://internal/foo.jpg") is None


def test_remote_enabled_blocks_private(monkeypatch):
    monkeypatch.setenv("VF_ALLOW_REMOTE_ASSET_FETCH", "true")
    with mock.patch.object(
        asset_fetch.socket,
        "getaddrinfo",
        return_value=[(socket.AF_INET, None, None, "", ("10.0.0.5", 0))],
    ):
        assert asset_fetch.fetch_asset_bytes("http://internal-vpn/foo.jpg") is None


def test_remote_enabled_blocks_link_local(monkeypatch):
    monkeypatch.setenv("VF_ALLOW_REMOTE_ASSET_FETCH", "true")
    with mock.patch.object(
        asset_fetch.socket,
        "getaddrinfo",
        return_value=[(socket.AF_INET, None, None, "", ("169.254.169.254", 0))],
    ):
        # AWS metadata service exact target — must be blocked.
        assert asset_fetch.fetch_asset_bytes("http://169.254.169.254/latest/meta-data") is None


def test_local_file_under_cap(monkeypatch, tmp_path):
    monkeypatch.delenv("VF_ALLOW_REMOTE_ASSET_FETCH", raising=False)
    f = tmp_path / "img.bin"
    f.write_bytes(b"PNG\x89data")
    data = asset_fetch.fetch_asset_bytes(str(f))
    assert data == b"PNG\x89data"


def test_local_file_over_cap_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("VF_MAX_ASSET_BYTES", "8")
    monkeypatch.delenv("VF_ALLOW_REMOTE_ASSET_FETCH", raising=False)
    f = tmp_path / "big.bin"
    f.write_bytes(b"\x00" * 64)
    assert asset_fetch.fetch_asset_bytes(str(f)) is None
    # Restore default for other tests in the suite.
    os.environ.pop("VF_MAX_ASSET_BYTES", None)


def test_object_store_path_falls_through_to_minio_helper():
    """A bare key (no scheme, no on-disk match) should hit MinIO; we mock it."""
    with mock.patch("app.services.storage.get_minio_client") as mocked:
        client = mock.Mock()
        resp = mock.Mock()
        resp.read.return_value = b"BLOB"
        client.get_object.return_value = resp
        mocked.return_value = client
        data = asset_fetch.fetch_asset_bytes("datasets/abc/img.jpg")
    assert data == b"BLOB"
