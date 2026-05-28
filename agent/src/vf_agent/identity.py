"""Persistent agent identity: cluster_id + register_token granted at adoption."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

IDENTITY_PATH = Path(os.getenv("VF_AGENT_IDENTITY_PATH", "/var/lib/vf-agent/identity.json"))


@dataclass
class Identity:
    cluster_id: str
    register_token: str
    api_url: str


def load() -> Optional[Identity]:
    if not IDENTITY_PATH.exists():
        return None
    try:
        data = json.loads(IDENTITY_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return Identity(
            cluster_id=data["cluster_id"],
            register_token=data["register_token"],
            api_url=data["api_url"],
        )
    except KeyError:
        return None


def save(identity: Identity) -> None:
    IDENTITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDENTITY_PATH.write_text(json.dumps(asdict(identity), indent=2))
    os.chmod(IDENTITY_PATH, 0o600)


def clear() -> None:
    if IDENTITY_PATH.exists():
        IDENTITY_PATH.unlink()
