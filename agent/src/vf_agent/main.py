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

from vf_agent import identity

logger = logging.getLogger("vf_agent.main")

HTTP_PORT = int(os.getenv("VF_AGENT_PORT", "9443"))
HTTP_HOST = os.getenv("VF_AGENT_HOST", "0.0.0.0")  # noqa: S104 - intended; agent serves on LAN
WAIT_FOR_IDENTITY_S = float(os.getenv("VF_AGENT_ADOPT_POLL", "2"))


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


def _wait_for_identity() -> identity.Identity:
    logger.info("waiting for adoption (POST /adopt on the HTTP server)...")
    while True:
        ident = identity.load()
        if ident is not None:
            logger.info("adopted as cluster %s", ident.cluster_id)
            return ident
        time.sleep(WAIT_FOR_IDENTITY_S)


def run() -> int:
    logging.basicConfig(
        level=os.getenv("VF_AGENT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not os.getenv("VF_AGENT_TOKEN"):
        logger.error("VF_AGENT_TOKEN is not set; refusing to start")
        return 2

    http = _spawn_http()
    ident = _wait_for_identity()
    heartbeat = _spawn_heartbeat()
    celery_proc = _spawn_celery(ident)

    children: list[subprocess.Popen[bytes]] = [http, heartbeat, celery_proc]

    def _shutdown(*_: object) -> None:
        logger.info("shutting down agent")
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    exit_code = 0
    try:
        while True:
            for child in children:
                ret = child.poll()
                if ret is not None:
                    logger.error("child process exited with code %s; tearing down", ret)
                    exit_code = ret or 1
                    raise SystemExit(exit_code)
            time.sleep(2)
    except SystemExit:
        _shutdown()
        return exit_code


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
