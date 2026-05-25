"""Public endpoints for the cluster agent installer.

The worker machine fetches `/api/agents/install.sh` via curl and pipes it to
bash. It is intentionally **unauthenticated** because (a) the worker has no
platform credentials yet and (b) the script contains no secrets — the
operator supplies `VF_AGENT_TOKEN` as an environment variable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])

INSTALL_SCRIPT = Path(__file__).resolve().parents[3].parent / "agent" / "scripts" / "install.sh"


@router.get("/install.sh", response_class=PlainTextResponse)
def get_install_script() -> PlainTextResponse:
    """Return the agent installer shell script.

    Served as `text/x-shellscript; charset=utf-8` so `curl | bash` works and
    browsers display it inline rather than offering a download.
    """
    body = INSTALL_SCRIPT.read_text(encoding="utf-8")
    return PlainTextResponse(
        content=body,
        media_type="text/x-shellscript; charset=utf-8",
    )
