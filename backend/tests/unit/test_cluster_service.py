from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as _models  # noqa: F401  ensure models are registered
from app.db.base import Base
from app.schemas.cluster import ClusterCreate, ClusterHeartbeat, GpuInfo
from app.services import cluster_service


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _create(db, **overrides):
    fields = {
        "name": "rig-01",
        "kind": "both",
        "cpu_cores": 16,
        "ram_total_mb": 32768,
        "disk_total_gb": 500,
        "gpu_vendor": "nvidia",
        "gpu_count": 2,
        "gpu_model": "A100",
        "gpu_memory_mb": 80 * 1024,
        **overrides,
    }
    payload = ClusterCreate(**fields)
    return cluster_service.create_cluster(db, payload)


def test_create_cluster_assigns_token_and_starts_offline(db):
    cluster = _create(db)
    assert cluster.id
    assert cluster.register_token
    assert cluster.status == "offline"
    assert cluster.gpu_vendor == "nvidia"
    assert cluster.enabled is True


def test_heartbeat_marks_online_and_records_telemetry(db):
    cluster = _create(db)
    payload = ClusterHeartbeat(
        register_token=cluster.register_token,
        status="online",
        cpu_usage_pct=42.5,
        ram_used_mb=4096,
        disk_used_gb=120,
        gpu_usage_pct=71.0,
        gpus=[GpuInfo(index=0, name="A100", memory_mb=81920, util_pct=71.0, mem_used_mb=4096)],
    )
    updated = cluster_service.record_heartbeat(db, cluster.id, payload)
    assert updated is not None
    assert updated.status == "online"
    assert updated.cpu_usage_pct == 42.5
    assert updated.gpu_usage_pct == 71.0
    assert updated.last_heartbeat_at is not None
    # gpus_json round-trip
    assert "A100" in (updated.gpus_json or "")


def test_heartbeat_rejects_bad_token(db):
    cluster = _create(db)
    payload = ClusterHeartbeat(register_token="WRONG", status="online")
    with pytest.raises(cluster_service.ClusterError):
        cluster_service.record_heartbeat(db, cluster.id, payload)


def test_is_available_requires_online_idle_and_fresh_heartbeat(db):
    cluster = _create(db)
    # offline → not available
    assert not cluster_service.is_available(cluster, kind="train")

    # online + recent heartbeat → available
    cluster_service.record_heartbeat(
        db,
        cluster.id,
        ClusterHeartbeat(register_token=cluster.register_token, status="online"),
    )
    db.refresh(cluster)
    assert cluster_service.is_available(cluster, kind="train")

    # disabled → unavailable
    cluster.enabled = False
    db.add(cluster)
    db.commit()
    assert not cluster_service.is_available(cluster, kind="train")


def test_is_available_filters_by_kind(db):
    cluster = _create(db, kind="eval")
    cluster_service.record_heartbeat(
        db,
        cluster.id,
        ClusterHeartbeat(register_token=cluster.register_token, status="online"),
    )
    db.refresh(cluster)
    assert cluster_service.is_available(cluster, kind="eval")
    assert not cluster_service.is_available(cluster, kind="train")


def test_reserve_marks_busy_and_blocks_double_booking(db):
    cluster = _create(db)
    cluster_service.record_heartbeat(
        db,
        cluster.id,
        ClusterHeartbeat(register_token=cluster.register_token, status="online"),
    )
    db.refresh(cluster)

    reserved = cluster_service.reserve_cluster(db, cluster.id, "job-1", kind="train")
    assert reserved.status == "busy"
    assert reserved.active_job_id == "job-1"

    with pytest.raises(cluster_service.ClusterNotAvailableError):
        cluster_service.reserve_cluster(db, cluster.id, "job-2", kind="train")


def test_release_returns_cluster_to_online(db):
    cluster = _create(db)
    cluster_service.record_heartbeat(
        db,
        cluster.id,
        ClusterHeartbeat(register_token=cluster.register_token, status="online"),
    )
    db.refresh(cluster)
    cluster_service.reserve_cluster(db, cluster.id, "job-1", kind="train")
    released = cluster_service.release_cluster(db, cluster.id)
    assert released is not None
    assert released.active_job_id is None
    assert released.status == "online"


def test_stale_heartbeat_treated_as_offline(db):
    cluster = _create(db)
    cluster_service.record_heartbeat(
        db,
        cluster.id,
        ClusterHeartbeat(register_token=cluster.register_token, status="online"),
    )
    # backdate the heartbeat past the timeout window
    db.refresh(cluster)
    cluster.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=600)
    db.add(cluster)
    db.commit()
    listed = cluster_service.list_clusters(db)
    assert listed[0].status == "offline"
    assert not cluster_service.is_available(listed[0], kind="train")
