from __future__ import annotations

import json

import httpx
import pytest

from vf_agent import heartbeat, identity


def _identity() -> identity.Identity:
    return identity.Identity(
        cluster_id="c-1",
        register_token="tok",
        api_url="http://platform:8000",
    )


def test_send_once_posts_correct_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.read().decode()
        return httpx.Response(202, json={"ok": True})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        code = heartbeat.send_once(_identity(), client=client)

    assert code == 202
    assert captured["url"] == "http://platform:8000/api/clusters/c-1/heartbeat"
    body = captured["json"]
    assert isinstance(body, str)
    # Parse the JSON rather than substring-matching the serialized form, which
    # is brittle against httpx/json separator whitespace differences.
    payload = json.loads(body)
    assert payload["register_token"] == "tok"
    assert payload["status"] == "online"


def test_send_once_transport_error_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        code = heartbeat.send_once(_identity(), client=client)
    assert code == 0
