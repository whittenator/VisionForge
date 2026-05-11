from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.schemas.cluster import (
    AgentInfo,
    ClusterCreate,
    ClusterDiscoverRequest,
    ClusterHeartbeat,
    ClusterUpdate,
)

# Heartbeat freshness window: a cluster is treated as offline if no heartbeat
# was received within this window, regardless of last persisted status.
HEARTBEAT_TIMEOUT = timedelta(seconds=90)

# Agent discovery timeouts. Kept short so an unreachable host returns quickly.
DISCOVER_TIMEOUT = 5.0


class ClusterError(Exception):
    pass


class ClusterNotAvailableError(ClusterError):
    pass


class AgentUnreachableError(ClusterError):
    """Raised when the discover flow can't reach or authenticate against an agent."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason  # one of: connect | timeout | auth | bad_response


def create_cluster(db: Session, payload: ClusterCreate) -> Cluster:
    cluster = Cluster(
        name=payload.name,
        description=payload.description,
        kind=payload.kind,
        cpu_cores=payload.cpu_cores,
        ram_total_mb=payload.ram_total_mb,
        disk_total_gb=payload.disk_total_gb,
        gpu_vendor=payload.gpu_vendor,
        gpu_count=payload.gpu_count,
        gpu_model=payload.gpu_model,
        gpu_memory_mb=payload.gpu_memory_mb,
        agent_host=payload.agent_host,
        agent_port=payload.agent_port,
        agent_version=payload.agent_version,
        os_name=payload.os_name,
        os_release=payload.os_release,
        arch=payload.arch,
        status="offline",
    )
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def _probe_agent(
    host: str,
    port: int,
    agent_token: str,
    *,
    scheme: str = "http",
    client: httpx.Client | None = None,
) -> AgentInfo:
    """Call the agent's /info endpoint. Raises AgentUnreachableError on failure."""
    base = f"{scheme}://{host}:{port}"
    headers = {"Authorization": f"Bearer {agent_token}"}
    own = client is None
    c = client or httpx.Client(timeout=DISCOVER_TIMEOUT)
    try:
        resp = c.get(f"{base}/info", headers=headers)
    except httpx.TimeoutException as exc:
        raise AgentUnreachableError("timeout", f"agent {host}:{port} timed out") from exc
    except httpx.ConnectError as exc:
        raise AgentUnreachableError("connect", f"agent {host}:{port} not reachable") from exc
    except httpx.HTTPError as exc:
        raise AgentUnreachableError("connect", str(exc)) from exc
    finally:
        if own:
            c.close()

    if resp.status_code in (401, 403):
        raise AgentUnreachableError("auth", "agent rejected the supplied agent token")
    if resp.status_code != 200:
        raise AgentUnreachableError(
            "bad_response", f"agent returned HTTP {resp.status_code}: {resp.text[:200]}"
        )
    try:
        return AgentInfo.model_validate(resp.json())
    except Exception as exc:
        raise AgentUnreachableError("bad_response", f"agent /info malformed: {exc}") from exc


def _adopt_agent(
    host: str,
    port: int,
    agent_token: str,
    cluster_id: str,
    register_token: str,
    api_url: str,
    *,
    scheme: str = "http",
    client: httpx.Client | None = None,
) -> None:
    base = f"{scheme}://{host}:{port}"
    headers = {"Authorization": f"Bearer {agent_token}"}
    body = {"cluster_id": cluster_id, "register_token": register_token, "api_url": api_url}
    own = client is None
    c = client or httpx.Client(timeout=DISCOVER_TIMEOUT)
    try:
        resp = c.post(f"{base}/adopt", headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise AgentUnreachableError("connect", f"adopt failed: {exc}") from exc
    finally:
        if own:
            c.close()
    if resp.status_code >= 400:
        raise AgentUnreachableError("bad_response", f"adopt rejected: HTTP {resp.status_code}")


def discover_cluster(
    db: Session,
    payload: ClusterDiscoverRequest,
    *,
    api_url: str,
    client: httpx.Client | None = None,
) -> Cluster:
    """Probe an agent, create a Cluster row from its /info, then adopt it.

    `api_url` is the publicly-reachable base URL of the platform (e.g.
    `http://platform:8000`); this gets persisted on the agent so it knows
    where to send heartbeats.
    """
    info = _probe_agent(
        payload.host,
        payload.port,
        payload.agent_token,
        scheme=payload.scheme,
        client=client,
    )

    os_meta = info.os or {}
    create_payload = ClusterCreate(
        name=payload.name,
        description=payload.description,
        kind=payload.kind,
        cpu_cores=info.cpu_cores,
        ram_total_mb=info.ram_total_mb,
        disk_total_gb=info.disk_total_gb,
        gpu_vendor=info.gpu_vendor,
        gpu_count=info.gpu_count,
        gpu_model=info.gpu_model,
        gpu_memory_mb=info.gpu_memory_mb,
        agent_host=payload.host,
        agent_port=payload.port,
        agent_version=info.agent_version,
        os_name=str(os_meta.get("name") or "") or None,
        os_release=str(os_meta.get("release") or "") or None,
        arch=str(os_meta.get("arch") or "") or None,
    )
    cluster = create_cluster(db, create_payload)

    # Persist the per-GPU breakdown so the UI can display it before the first heartbeat.
    if info.gpus:
        cluster.gpus_json = json.dumps([g.model_dump() for g in info.gpus])
        db.add(cluster)
        db.commit()
        db.refresh(cluster)

    _adopt_agent(
        payload.host,
        payload.port,
        payload.agent_token,
        cluster.id,
        cluster.register_token,
        api_url,
        scheme=payload.scheme,
        client=client,
    )
    return cluster


def update_cluster(db: Session, cluster_id: str, payload: ClusterUpdate) -> Cluster | None:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        return None
    if payload.name is not None:
        cluster.name = payload.name
    if payload.description is not None:
        cluster.description = payload.description
    if payload.kind is not None:
        cluster.kind = payload.kind
    if payload.enabled is not None:
        cluster.enabled = payload.enabled
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def delete_cluster(db: Session, cluster_id: str) -> bool:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        return False
    db.delete(cluster)
    db.commit()
    return True


def list_clusters(db: Session) -> list[Cluster]:
    rows = db.scalars(select(Cluster).order_by(Cluster.name)).all()
    # Auto-degrade stale heartbeats so the API surface reflects reality without
    # requiring a separate sweeper task.
    cutoff = datetime.now(timezone.utc) - HEARTBEAT_TIMEOUT
    changed = False
    for c in rows:
        if c.status in ("online", "busy") and (
            c.last_heartbeat_at is None or _aware(c.last_heartbeat_at) < cutoff
        ):
            c.status = "offline"
            changed = True
    if changed:
        db.commit()
    return list(rows)


def get_cluster(db: Session, cluster_id: str) -> Cluster | None:
    return db.get(Cluster, cluster_id)


def record_heartbeat(db: Session, cluster_id: str, payload: ClusterHeartbeat) -> Cluster | None:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        return None
    if payload.register_token != cluster.register_token:
        raise ClusterError("invalid register_token")

    cluster.cpu_usage_pct = float(payload.cpu_usage_pct)
    cluster.ram_used_mb = int(payload.ram_used_mb)
    cluster.disk_used_gb = int(payload.disk_used_gb)
    cluster.gpu_usage_pct = float(payload.gpu_usage_pct)

    if payload.gpus is not None:
        cluster.gpus_json = json.dumps([g.model_dump() for g in payload.gpus])

    # Optional capacity refresh
    if payload.cpu_cores is not None:
        cluster.cpu_cores = payload.cpu_cores
    if payload.ram_total_mb is not None:
        cluster.ram_total_mb = payload.ram_total_mb
    if payload.disk_total_gb is not None:
        cluster.disk_total_gb = payload.disk_total_gb
    if payload.gpu_vendor is not None:
        cluster.gpu_vendor = payload.gpu_vendor
    if payload.gpu_count is not None:
        cluster.gpu_count = payload.gpu_count
    if payload.gpu_model is not None:
        cluster.gpu_model = payload.gpu_model
    if payload.gpu_memory_mb is not None:
        cluster.gpu_memory_mb = payload.gpu_memory_mb

    # If the agent reports busy/error, keep that; otherwise flip to online unless
    # there's an active job (busy) attached.
    if payload.status == "error":
        cluster.status = "error"
    elif cluster.active_job_id:
        cluster.status = "busy"
    else:
        cluster.status = payload.status if payload.status != "offline" else "online"

    cluster.last_heartbeat_at = datetime.now(timezone.utc)
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def is_available(cluster: Cluster, *, kind: str | None = None) -> bool:
    """A cluster is available if enabled, online, idle, and matches the workload kind."""
    if not cluster.enabled:
        return False
    if cluster.status != "online":
        return False
    if cluster.active_job_id:
        return False
    if cluster.last_heartbeat_at is None:
        return False
    if _aware(cluster.last_heartbeat_at) < datetime.now(timezone.utc) - HEARTBEAT_TIMEOUT:
        return False
    if kind and cluster.kind not in (kind, "both"):
        return False
    return True


def list_available(db: Session, *, kind: str | None = None) -> list[Cluster]:
    return [c for c in list_clusters(db) if is_available(c, kind=kind)]


def reserve_cluster(
    db: Session,
    cluster_id: str,
    job_id: str,
    *,
    kind: str | None = None,
) -> Cluster:
    """Atomically mark the cluster busy with the given job; raise if not available."""
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise ClusterNotAvailableError(f"cluster {cluster_id} not found")
    if not is_available(cluster, kind=kind):
        raise ClusterNotAvailableError(
            f"cluster {cluster.name} is not available for {kind or 'this workload'}"
        )
    cluster.active_job_id = job_id
    cluster.status = "busy"
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def release_cluster(db: Session, cluster_id: str) -> Cluster | None:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        return None
    cluster.active_job_id = None
    if cluster.status == "busy":
        cluster.status = "online"
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def rotate_register_token(db: Session, cluster_id: str) -> Cluster | None:
    import secrets

    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        return None
    cluster.register_token = secrets.token_urlsafe(32)
    # Force the agent to re-adopt by treating the cluster as offline until next heartbeat.
    cluster.status = "offline"
    cluster.last_heartbeat_at = None
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def _aware(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to UTC-aware for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def summarize(clusters: Iterable[Cluster], *, kind: str | None = None) -> list[dict]:
    out = []
    for c in clusters:
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "kind": c.kind,
                "status": c.status,
                "enabled": c.enabled,
                "gpu_vendor": c.gpu_vendor,
                "gpu_count": c.gpu_count,
                "gpu_model": c.gpu_model,
                "cpu_cores": c.cpu_cores,
                "ram_total_mb": c.ram_total_mb,
                "available": is_available(c, kind=kind),
            }
        )
    return out
