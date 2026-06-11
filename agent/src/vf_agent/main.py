"""Agent supervisor: starts the HTTP server, waits for adoption, then launches
the heartbeat loop and Celery worker bound to this cluster's queue.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable

from vf_agent import identity

logger = logging.getLogger("vf_agent.main")

HTTP_PORT = int(os.getenv("VF_AGENT_PORT", "9443"))
HTTP_HOST = os.getenv("VF_AGENT_HOST", "0.0.0.0")  # noqa: S104 - intended; agent serves on LAN
WAIT_FOR_IDENTITY_S = float(os.getenv("VF_AGENT_ADOPT_POLL", "2"))

# Respawn policy for child processes (HTTP server, heartbeat, celery worker).
RESPAWN_BACKOFF_INITIAL_S = 2.0
RESPAWN_BACKOFF_MAX_S = 60.0
RESPAWN_STABLE_AFTER_S = 300.0  # child stayed up this long -> reset its backoff
RESPAWN_MAX_CONSECUTIVE_FAILURES = 5


def _spawn_http() -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "vf_agent.server:app",
        "--host",
        HTTP_HOST,
        "--port",
        str(HTTP_PORT),
        "--log-level",
        os.getenv("VF_AGENT_LOG_LEVEL", "info").lower(),
    ]
    logger.info("starting agent HTTP server: %s", " ".join(cmd))
    return subprocess.Popen(cmd)


def _spawn_heartbeat() -> subprocess.Popen[bytes]:
    cmd = [sys.executable, "-m", "vf_agent.heartbeat"]
    logger.info("starting heartbeat loop")
    return subprocess.Popen(cmd)


def _spawn_celery(ident: identity.Identity) -> subprocess.Popen[bytes]:
    queue = f"cluster.{ident.cluster_id}"
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.jobs.celery_app",
        "worker",
        "-Q",
        queue,
        "--loglevel",
        os.getenv("VF_AGENT_LOG_LEVEL", "info").lower(),
        "--concurrency",
        os.getenv("VF_AGENT_CELERY_CONCURRENCY", "1"),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "/app/src")
    logger.info("starting celery worker bound to %s", queue)
    return subprocess.Popen(cmd, env=env)


class _Child:
    """A supervised child process with restart-with-backoff bookkeeping."""

    def __init__(self, name: str, spawn: Callable[[], subprocess.Popen[bytes]]) -> None:
        self.name = name
        self.spawn = spawn
        self.proc: subprocess.Popen[bytes] = spawn()
        self.started_at = time.monotonic()
        self.backoff_s = RESPAWN_BACKOFF_INITIAL_S
        self.consecutive_failures = 0

    def respawn(self) -> None:
        self.proc = self.spawn()
        self.started_at = time.monotonic()


def run() -> int:
    logging.basicConfig(
        level=os.getenv("VF_AGENT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not os.getenv("VF_AGENT_TOKEN"):
        logger.error("VF_AGENT_TOKEN is not set; refusing to start")
        return 2

    children: list[_Child] = []
    shutting_down = False

    def _shutdown(*_: object) -> None:
        nonlocal shutting_down
        shutting_down = True
        logger.info("shutting down agent")
        for child in children:
            if child.proc.poll() is None:
                child.proc.terminate()
        for child in children:
            try:
                child.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.proc.kill()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    def _supervise(child: _Child) -> None:
        """Check one child; respawn with backoff if it died.

        Raises SystemExit after RESPAWN_MAX_CONSECUTIVE_FAILURES consecutive
        failed respawns of the same child.
        """
        ret = child.proc.poll()
        if ret is None:
            # Child has stayed up long enough: consider it healthy again.
            if (
                child.consecutive_failures
                and time.monotonic() - child.started_at >= RESPAWN_STABLE_AFTER_S
            ):
                logger.info(
                    "child %s stable for %ss; resetting respawn backoff",
                    child.name,
                    int(RESPAWN_STABLE_AFTER_S),
                )
                child.consecutive_failures = 0
                child.backoff_s = RESPAWN_BACKOFF_INITIAL_S
            return

        if shutting_down:
            return

        child.consecutive_failures += 1
        if child.consecutive_failures > RESPAWN_MAX_CONSECUTIVE_FAILURES:
            logger.error(
                "child %s failed %s consecutive respawns (last exit code %s); "
                "giving up and tearing down",
                child.name,
                RESPAWN_MAX_CONSECUTIVE_FAILURES,
                ret,
            )
            raise SystemExit(ret or 1)

        logger.error(
            "child %s exited unexpectedly with code %s; respawning in %.0fs (attempt %s/%s)",
            child.name,
            ret,
            child.backoff_s,
            child.consecutive_failures,
            RESPAWN_MAX_CONSECUTIVE_FAILURES,
        )
        time.sleep(child.backoff_s)
        child.backoff_s = min(child.backoff_s * 2, RESPAWN_BACKOFF_MAX_S)
        if not shutting_down:
            child.respawn()

    exit_code = 0
    try:
        http = _Child("http", _spawn_http)
        children.append(http)

        # Adoption gate: only the HTTP server runs until the backend POSTs
        # /adopt. Keep supervising it (with respawn) while we wait.
        logger.info("waiting for adoption (POST /adopt on the HTTP server)...")
        ident: identity.Identity | None = None
        while not shutting_down:
            ident = identity.load()
            if ident is not None:
                logger.info("adopted as cluster %s", ident.cluster_id)
                break
            _supervise(http)
            time.sleep(WAIT_FOR_IDENTITY_S)
        if shutting_down or ident is None:
            return exit_code

        adopted = ident
        children.append(_Child("heartbeat", _spawn_heartbeat))
        children.append(_Child("celery", lambda: _spawn_celery(adopted)))

        while not shutting_down:
            for child in children:
                _supervise(child)
            time.sleep(2)
        return exit_code
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 1
        _shutdown()
        return exit_code


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
