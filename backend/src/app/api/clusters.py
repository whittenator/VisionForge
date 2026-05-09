from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.cluster import Cluster as ClusterSchema
from app.schemas.cluster import (
    ClusterCreate,
    ClusterHeartbeat,
    ClusterHeartbeatAck,
    ClusterRegistration,
    ClusterSummary,
    ClusterUpdate,
    cluster_to_dict,
)
from app.services import cluster_service

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterSchema])
def list_clusters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = cluster_service.list_clusters(db)
    return [ClusterSchema(**cluster_to_dict(c)) for c in rows]


@router.get("/available", response_model=list[ClusterSummary])
def list_available_clusters(
    kind: str | None = Query(
        None,
        pattern="^(train|eval|both)$",
        description="Filter to clusters that can run this workload kind.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return clusters that are online, idle, and able to accept work.

    Used by the training and evaluation forms to populate the cluster picker.
    """
    rows = cluster_service.list_clusters(db)
    return [ClusterSummary(**s) for s in cluster_service.summarize(rows, kind=kind)]


@router.post("", response_model=ClusterRegistration, status_code=201)
def create_cluster(
    payload: ClusterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = cluster_service.create_cluster(db, payload)
    data = cluster_to_dict(cluster)
    data["register_token"] = cluster.register_token
    return ClusterRegistration(**data)


@router.get("/{cluster_id}", response_model=ClusterSchema)
def get_cluster(
    cluster_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = cluster_service.get_cluster(db, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return ClusterSchema(**cluster_to_dict(cluster))


@router.patch("/{cluster_id}", response_model=ClusterSchema)
def update_cluster(
    payload: ClusterUpdate,
    cluster_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cluster = cluster_service.update_cluster(db, cluster_id, payload)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return ClusterSchema(**cluster_to_dict(cluster))


@router.delete("/{cluster_id}", status_code=204)
def delete_cluster(
    cluster_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not cluster_service.delete_cluster(db, cluster_id):
        raise HTTPException(status_code=404, detail="Cluster not found")


@router.post("/{cluster_id}/heartbeat", response_model=ClusterHeartbeatAck)
def heartbeat(
    payload: ClusterHeartbeat,
    cluster_id: str = Path(...),
    db: Session = Depends(get_db),
):
    """Endpoint called by the cluster agent every N seconds with telemetry.

    Authenticates via the cluster's `register_token` (returned on creation).
    Does not require a logged-in user, since the agent runs unattended.
    """
    try:
        cluster = cluster_service.record_heartbeat(db, cluster_id, payload)
    except cluster_service.ClusterError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return ClusterHeartbeatAck(
        cluster_id=cluster.id,
        status=cluster.status,
        server_time=datetime.now(timezone.utc),
    )


@router.post("/{cluster_id}/release", response_model=ClusterSchema)
def release(
    cluster_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually release a cluster (e.g. if a job died without cleaning up)."""
    cluster = cluster_service.release_cluster(db, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return ClusterSchema(**cluster_to_dict(cluster))
