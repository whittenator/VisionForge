"""Unit tests for the agent's persistent identity store.

``identity`` reads/writes a small JSON file granted at adoption. We point the
module-level path at a tmp file and verify the save/load round-trip, the
0600 permission bits, and graceful handling of missing/corrupt files.
"""

from __future__ import annotations

import json
import stat

from vf_agent import identity
from vf_agent.identity import Identity


def _redirect(monkeypatch, tmp_path):
    path = tmp_path / "identity.json"
    monkeypatch.setattr(identity, "IDENTITY_PATH", path)
    return path


def test_load_returns_none_when_absent(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    assert identity.load() is None


def test_save_then_load_round_trips(monkeypatch, tmp_path):
    path = _redirect(monkeypatch, tmp_path)
    ident = Identity(cluster_id="c1", register_token="tok", api_url="https://api")
    identity.save(ident)

    assert path.exists()
    loaded = identity.load()
    assert loaded == ident
    assert loaded.cluster_id == "c1"
    assert loaded.register_token == "tok"


def test_save_sets_owner_only_permissions(monkeypatch, tmp_path):
    path = _redirect(monkeypatch, tmp_path)
    identity.save(Identity(cluster_id="c", register_token="t", api_url="u"))
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_load_returns_none_on_corrupt_json(monkeypatch, tmp_path):
    path = _redirect(monkeypatch, tmp_path)
    path.write_text("{ not valid json")
    assert identity.load() is None


def test_load_returns_none_on_missing_keys(monkeypatch, tmp_path):
    path = _redirect(monkeypatch, tmp_path)
    path.write_text(json.dumps({"cluster_id": "c"}))  # missing register_token/api_url
    assert identity.load() is None


def test_clear_removes_file(monkeypatch, tmp_path):
    path = _redirect(monkeypatch, tmp_path)
    identity.save(Identity(cluster_id="c", register_token="t", api_url="u"))
    assert path.exists()
    identity.clear()
    assert not path.exists()
    # Clearing again is a no-op, not an error.
    identity.clear()
