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


def test_discover_probes_agent_and_creates_cluster(db):
    import httpx

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path.endswith("/info"):
            assert request.headers.get("authorization") == "Bearer agent-secret"
            return httpx.Response(
                200,
                json={
                    "cpu_cores": 32,
                    "ram_total_mb": 65536,
                    "disk_total_gb": 1000,
                    "gpu_vendor": "nvidia",
                    "gpu_count": 2,
                    "gpu_model": "A100 80GB",
                    "gpu_memory_mb": 81920,
                    "gpus": [
                        {"index": 0, "name": "A100", "memory_mb": 81920, "util_pct": 0.0},
                        {"index": 1, "name": "A100", "memory_mb": 81920, "util_pct": 0.0},
                    ],
                    "cpu_usage_pct": 0.0,
                    "ram_used_mb": 0,
                    "disk_used_gb": 0,
                    "gpu_usage_pct": 0.0,
                    "os": {"name": "Linux", "release": "6.18.5", "arch": "x86_64"},
                    "agent_version": "0.1.0",
                },
            )
        if request.url.path.endswith("/adopt"):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        from app.schemas.cluster import ClusterDiscoverRequest

        cluster = cluster_service.discover_cluster(
            db,
            ClusterDiscoverRequest(
                name="rig-01",
                host="10.0.0.10",
                port=9443,
                agent_token="agent-secret",
                kind="both",
            ),
            api_url="http://platform:8000",
            client=client,
        )

    assert cluster.cpu_cores == 32
    assert cluster.ram_total_mb == 65536
    assert cluster.gpu_vendor == "nvidia"
    assert cluster.gpu_count == 2
    assert cluster.gpu_model == "A100 80GB"
    assert cluster.agent_host == "10.0.0.10"
    assert cluster.agent_port == 9443
    assert cluster.agent_version == "0.1.0"
    assert cluster.os_name == "Linux"
    assert cluster.os_release == "6.18.5"
    assert cluster.arch == "x86_64"
    assert cluster.gpus_json and "A100" in cluster.gpus_json

    # Both /info and /adopt were called.
    paths = [r.url.path for r in captured]
    assert "/info" in paths
    assert "/adopt" in paths


def test_discover_returns_connect_error_when_agent_down(db):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    from app.schemas.cluster import ClusterDiscoverRequest

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(cluster_service.AgentUnreachableError) as exc:
            cluster_service.discover_cluster(
                db,
                ClusterDiscoverRequest(
                    name="x", host="h", port=9443, agent_token="t", kind="both"
                ),
                api_url="http://platform:8000",
                client=client,
            )
    assert exc.value.reason == "connect"


def test_discover_returns_auth_error_on_401(db):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "bad token"})

    from app.schemas.cluster import ClusterDiscoverRequest

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(cluster_service.AgentUnreachableError) as exc:
            cluster_service.discover_cluster(
                db,
                ClusterDiscoverRequest(
                    name="x", host="h", port=9443, agent_token="wrong", kind="both"
                ),
                api_url="http://platform:8000",
                client=client,
            )
    assert exc.value.reason == "auth"


def test_rotate_register_token_invalidates_old_token(db):
    cluster = _create(db)
    old_token = cluster.register_token
    rotated = cluster_service.rotate_register_token(db, cluster.id)
    assert rotated is not None
    assert rotated.register_token != old_token
    assert rotated.status == "offline"
    # Old token now fails heartbeats
    with pytest.raises(cluster_service.ClusterError):
        cluster_service.record_heartbeat(
            db,
            cluster.id,
            ClusterHeartbeat(register_token=old_token, status="online"),
        )


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
