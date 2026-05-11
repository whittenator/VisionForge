"""Heartbeat loop: pushes telemetry to the platform every N seconds."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from vf_agent import discover, identity

logger = logging.getLogger("vf_agent.heartbeat")

HEARTBEAT_INTERVAL_S = int(os.getenv("VF_AGENT_HEARTBEAT_INTERVAL", "30"))
HEARTBEAT_TIMEOUT_S = float(os.getenv("VF_AGENT_HEARTBEAT_TIMEOUT", "10"))


def _payload(ident: identity.Identity) -> dict[str, Any]:
    snap = discover.discover()
    return {
        "register_token": ident.register_token,
        "status": "online",
        "cpu_usage_pct": snap["cpu_usage_pct"],
        "ram_used_mb": snap["ram_used_mb"],
        "disk_used_gb": snap["disk_used_gb"],
        "gpu_usage_pct": snap["gpu_usage_pct"],
        "gpus": snap["gpus"],
        "cpu_cores": snap["cpu_cores"],
        "ram_total_mb": snap["ram_total_mb"],
        "disk_total_gb": snap["disk_total_gb"],
        "gpu_vendor": snap["gpu_vendor"],
        "gpu_count": snap["gpu_count"],
        "gpu_model": snap["gpu_model"],
        "gpu_memory_mb": snap["gpu_memory_mb"],
    }


def send_once(ident: identity.Identity, *, client: httpx.Client | None = None) -> int:
    """Send a single heartbeat. Returns HTTP status code (0 on transport error)."""
    url = f"{ident.api_url}/api/clusters/{ident.cluster_id}/heartbeat"
    own = client is None
    c = client or httpx.Client(timeout=HEARTBEAT_TIMEOUT_S)
    try:
        resp = c.post(url, json=_payload(ident))
        return resp.status_code
    except httpx.HTTPError as exc:
        logger.warning("heartbeat transport error: %s", exc)
        return 0
    finally:
        if own:
            c.close()


def run_forever() -> None:
    """Block forever, posting heartbeats. Waits for identity to exist before starting."""
    logging.basicConfig(level=os.getenv("VF_AGENT_LOG_LEVEL", "INFO"))
    while True:
        ident = identity.load()
        if ident is None:
            time.sleep(2)
            continue
        with httpx.Client(timeout=HEARTBEAT_TIMEOUT_S) as client:
            while True:
                code = send_once(ident, client=client)
                if code == 0:
                    logger.warning("heartbeat failed (transport)")
                elif code >= 400:
                    logger.warning("heartbeat failed: HTTP %s", code)
                else:
                    logger.debug("heartbeat ok: %s", code)
                time.sleep(HEARTBEAT_INTERVAL_S)


def main() -> None:
    run_forever()


if __name__ == "__main__":
    main()
