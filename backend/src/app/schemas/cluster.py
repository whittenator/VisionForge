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
    """Internal-only creation payload used by the discovery service.

    The public API does not accept manually-entered hardware specs anymore;
    clients should call POST /api/clusters/discover instead, which probes the
    agent and fills these fields from the agent's /info response.
    """

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
    agent_host: str | None = None
    agent_port: int | None = None
    agent_version: str | None = None
    os_name: str | None = None
    os_release: str | None = None
    arch: str | None = None


class ClusterDiscoverRequest(BaseModel):
    """Operator-supplied tuple used to reach a running agent on the worker."""

    name: str = Field(..., min_length=1, max_length=255)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(9443, ge=1, le=65535)
    agent_token: str = Field(..., min_length=1)
    kind: ClusterKind = "both"
    description: str | None = None
    scheme: Literal["http", "https"] = "http"


class AgentInfo(BaseModel):
    """Schema for the JSON returned by the agent's `/info` endpoint."""

    cpu_cores: int = 0
    ram_total_mb: int = 0
    disk_total_gb: int = 0
    gpu_vendor: GpuVendor = "cpu"
    gpu_count: int = 0
    gpu_model: str | None = None
    gpu_memory_mb: int = 0
    gpus: list[GpuInfo] = Field(default_factory=list)
    cpu_usage_pct: float = 0.0
    ram_used_mb: int = 0
    disk_used_gb: int = 0
    gpu_usage_pct: float = 0.0
    os: dict[str, Any] = Field(default_factory=dict)
    agent_version: str | None = None


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

    agent_host: str | None = None
    agent_port: int | None = None
    agent_version: str | None = None
    os_name: str | None = None
    os_release: str | None = None
    arch: str | None = None


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
        "agent_host": getattr(model, "agent_host", None),
        "agent_port": getattr(model, "agent_port", None),
        "agent_version": getattr(model, "agent_version", None),
        "os_name": getattr(model, "os_name", None),
        "os_release": getattr(model, "os_release", None),
        "arch": getattr(model, "arch", None),
    }
