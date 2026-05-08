from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ClusterKind = Literal["train", "eval", "both"]
ClusterStatus = Literal["online", "offline", "busy", "error"]
GpuVendor = Literal["nvidia", "rocm", "cpu"]


class GpuInfo(BaseModel):
    """Per-GPU telemetry reported by the agent."""

    index: int
    name: str | None = None
    memory_mb: int = 0
    util_pct: float = 0.0
    mem_used_mb: int = 0
    temperature_c: float | None = None


class ClusterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    kind: ClusterKind = "both"
    cpu_cores: int = 0
    ram_total_mb: int = 0
    disk_total_gb: int = 0
    gpu_vendor: GpuVendor = "cpu"
    gpu_count: int = 0
    gpu_model: str | None = None
    gpu_memory_mb: int = 0


class ClusterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    kind: ClusterKind | None = None
    enabled: bool | None = None


class ClusterHeartbeat(BaseModel):
    """Telemetry payload sent periodically by the agent on a cluster.

    The agent authenticates by including the cluster's `register_token`.
    """

    register_token: str
    status: ClusterStatus = "online"
    cpu_usage_pct: float = 0.0
    ram_used_mb: int = 0
    disk_used_gb: int = 0
    gpu_usage_pct: float = 0.0
    gpus: list[GpuInfo] | None = None
    # Optional capacity refresh (in case hardware was reconfigured)
    cpu_cores: int | None = None
    ram_total_mb: int | None = None
    disk_total_gb: int | None = None
    gpu_vendor: GpuVendor | None = None
    gpu_count: int | None = None
    gpu_model: str | None = None
    gpu_memory_mb: int | None = None


class Cluster(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    kind: ClusterKind
    status: ClusterStatus
    enabled: bool

    cpu_cores: int
    ram_total_mb: int
    disk_total_gb: int

    gpu_vendor: GpuVendor
    gpu_count: int
    gpu_model: str | None = None
    gpu_memory_mb: int

    cpu_usage_pct: float
    ram_used_mb: int
    disk_used_gb: int
    gpu_usage_pct: float

    active_job_id: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime | None = None

    gpus: list[GpuInfo] = Field(default_factory=list)


class ClusterRegistration(Cluster):
    """Cluster representation returned on creation, including the secret token."""

    register_token: str


class ClusterSummary(BaseModel):
    """Lightweight cluster row used for selectors."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: ClusterKind
    status: ClusterStatus
    enabled: bool
    gpu_vendor: GpuVendor
    gpu_count: int
    gpu_model: str | None = None
    cpu_cores: int
    ram_total_mb: int
    available: bool


class ClusterHeartbeatAck(BaseModel):
    ok: bool = True
    cluster_id: str
    status: ClusterStatus
    server_time: datetime


def cluster_to_dict(model: Any) -> dict[str, Any]:
    """Convert a Cluster ORM row to the API dict (parsing gpus_json)."""
    import json

    gpus: list[dict[str, Any]] = []
    if getattr(model, "gpus_json", None):
        try:
            parsed = json.loads(model.gpus_json)
            if isinstance(parsed, list):
                gpus = parsed
        except Exception:
            gpus = []

    return {
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "kind": model.kind,
        "status": model.status,
        "enabled": model.enabled,
        "cpu_cores": model.cpu_cores,
        "ram_total_mb": model.ram_total_mb,
        "disk_total_gb": model.disk_total_gb,
        "gpu_vendor": model.gpu_vendor,
        "gpu_count": model.gpu_count,
        "gpu_model": model.gpu_model,
        "gpu_memory_mb": model.gpu_memory_mb,
        "cpu_usage_pct": model.cpu_usage_pct,
        "ram_used_mb": model.ram_used_mb,
        "disk_used_gb": model.disk_used_gb,
        "gpu_usage_pct": model.gpu_usage_pct,
        "active_job_id": model.active_job_id,
        "last_heartbeat_at": model.last_heartbeat_at,
        "created_at": model.created_at,
        "gpus": gpus,
    }
