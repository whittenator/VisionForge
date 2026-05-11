from __future__ import annotations

import secrets
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _token() -> str:
    return secrets.token_urlsafe(32)


class Cluster(Base):
    """Compute cluster (worker node / agent) used for training and evaluation jobs.

    A cluster represents one or more machines reachable by the platform that can
    execute training or evaluation tasks. Each cluster reports resource telemetry
    (CPU, RAM, disk, GPU) via heartbeat so the UI can show live availability and
    users can pick an idle cluster when launching a job.
    """

    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "train" | "eval" | "both"
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="both")
    # "online" | "offline" | "busy" | "error"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="offline")

    # Static capacity (reported on registration / refresh)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ram_total_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disk_total_gb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # GPU summary. vendor: "nvidia" | "rocm" | "cpu" (no GPU)
    gpu_vendor: Mapped[str] = mapped_column(String(16), nullable=False, default="cpu")
    gpu_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gpu_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gpu_memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # JSON array of per-GPU dicts: [{index, name, memory_mb, util_pct, mem_used_mb, temperature_c}, ...]
    gpus_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Live telemetry (last heartbeat)
    cpu_usage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ram_used_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disk_used_gb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gpu_usage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Active job tracking
    active_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Registration token used by the agent to authenticate heartbeats
    register_token: Mapped[str] = mapped_column(String(64), nullable=False, default=_token)

    # Agent reachability (populated by the discovery flow)
    agent_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # OS metadata reported by the agent at discovery time
    os_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_release: Mapped[str | None] = mapped_column(String(128), nullable=True)
    arch: Mapped[str | None] = mapped_column(String(32), nullable=True)

    last_heartbeat_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
