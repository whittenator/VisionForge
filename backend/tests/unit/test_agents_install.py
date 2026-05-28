"""Tests for the hosted agent installer endpoint."""

from tests.conftest import client


def test_install_script_served_as_shellscript():
    resp = client.get("/api/agents/install.sh")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/x-shellscript")
    body = resp.text
    assert body.startswith("#!/usr/bin/env bash")
    # Vendor branches must all be present so the curl|bash flow works for each.
    assert "visionforge/agent:nvidia" in body
    assert "visionforge/agent:rocm" in body
    assert "visionforge/agent:cpu" in body
    # The script must require the token rather than baking one in.
    assert "VF_AGENT_TOKEN" in body
    assert "VF_VENDOR" in body


def test_install_script_is_unauthenticated():
    # No Authorization header — the worker has no platform credentials yet.
    resp = client.get("/api/agents/install.sh")
    assert resp.status_code == 200
