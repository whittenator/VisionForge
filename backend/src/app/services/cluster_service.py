from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.schemas.cluster import (
    ClusterCreate,
    ClusterHeartbeat,
    ClusterUpdate,
)

# Heartbeat freshness window: a cluster is treated as offline if no heartbeat
# was received within this window, regardless of last persisted status.
HEARTBEAT_TIMEOUT = timedelta(seconds=90)


class ClusterError(Exception):
    pass


class ClusterNotAvailableError(ClusterError):
    pass


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
        status="offline",
    )
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
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
