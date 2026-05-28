# Feature Spec: Cluster Discovery & Agent Runtime

**Branch**: `claude/cluster-discovery-feature`
**Status**: In Progress
**Owners**: Platform team

## Summary

Replace the manual-entry cluster registration flow with **discovery-based registration**: operators run an unattended **agent** on a worker machine, then in the UI enter only the cluster name, host:port, and agent token. The backend reaches out to the agent's HTTP info endpoint, auto-populates hardware/OS specs, and adopts the agent for the cluster.

This closes the gap where the previous design referenced a `visionforge/agent:latest` image that did not exist in the repo, and required operators to type CPU/RAM/GPU specs by hand.

## Goals

1. Operators register a cluster with **only** a name + host + port + token.
2. Hardware (CPU/RAM/disk/GPU) and OS metadata are **auto-discovered** from a running agent.
3. The agent runs in Docker and bundles all of VisionForge's ML dependencies (PyTorch, Ultralytics, ONNX, open-clip) so it can execute training, evaluation, and ONNX export jobs.
4. Jobs continue to route via the existing per-cluster Celery queue (`cluster.{id}`).
5. The platform can detect an unreachable agent (timeout / connect refused / bad token) and surface a precise error reason to the UI.

## Non-Goals

- mTLS or signed-JWT auth between platform ↔ agent (HTTP + bearer token is sufficient for v1; agents are expected to be on a private network).
- Auto-update of the agent image. (Tracked under "agent version visibility" in Phase 5; in-place upgrades are future work.)
- Multi-tenant agent pools (one cluster row = one agent process).

## User Stories

- **As a platform admin** I install the agent on a new GPU box with a single `docker run`, paste the IP into the UI, and the cluster is registered with the correct specs without me typing them in.
- **As an ML engineer** launching a training run I see the cluster's discovered specs (CPU/RAM/GPU/OS) in the cluster picker so I can pick the right hardware.
- **As a security-conscious admin** I can rotate a cluster's `register_token` from the UI and immediately invalidate the old token, forcing the agent to be re-adopted.

## Architecture

```
┌───────────────────────────────┐     POST /api/clusters/discover     ┌─────────────────┐
│  Operator browser  (UI)       │ ───────────────────────────────────▶│  Platform API   │
└───────────────────────────────┘                                     │                 │
                                          GET  /info  (bearer agent)  │                 │
                                  ◀────────────────────────────────── │                 │
┌───────────────────────────────┐                                     │                 │
│  Worker machine               │   POST /adopt {cluster_id,token}    │                 │
│                               │ ◀────────────────────────────────── │                 │
│  ┌─────────────────────────┐  │                                     │                 │
│  │ vf-agent HTTP (9443)    │  │   POST /api/clusters/{id}/heartbeat │                 │
│  │ + heartbeat loop        │  │ ──────────────────────────────────▶ │                 │
│  │ + Celery worker         │  │                                     │                 │
│  │   (-Q cluster.{id})     │  │   pickup tasks from Redis           │  Redis + Celery │
│  └─────────────────────────┘  │ ◀────────────────────────────────── │                 │
└───────────────────────────────┘                                     └─────────────────┘
```

## Functional Requirements

| ID | Requirement |
|---|---|
| F1 | The agent exposes `GET /info` returning a JSON snapshot with `cpu_cores`, `ram_total_mb`, `disk_total_gb`, `gpu_vendor`, `gpu_count`, `gpu_model`, `gpu_memory_mb`, `gpus[]`, `os{name,release,arch}`, `agent_version`. |
| F2 | The agent exposes `GET /telemetry` returning current usage figures. |
| F3 | The agent exposes `POST /adopt` accepting `{cluster_id, register_token, api_url}` and persisting them to a volume. |
| F4 | `/info`, `/telemetry`, `/adopt` all require `Authorization: Bearer $VF_AGENT_TOKEN`. `/health` is unauthenticated. |
| F5 | `POST /api/clusters/discover` (auth: user) takes `{name, host, port, agent_token, kind, description?, scheme?, gpu_vendor?}`, calls the agent's `/info` then `/adopt`, persists a `Cluster` row, and returns it including `register_token`. |
| F6 | The platform returns HTTP 502 with a `[reason=connect\|timeout\|auth\|bad_response\|vendor_mismatch]` suffix when the agent is unreachable or its reported `gpu_vendor` disagrees with the operator's selection. |
| F7 | `POST /api/clusters/{id}/rotate-token` re-issues `register_token` and forces the cluster to `offline`, invalidating the agent's old token. |
| F8 | The agent's Celery worker subscribes to queue `cluster.{cluster_id}` only after adoption. |
| F9 | The cluster row stores `agent_host`, `agent_port`, `agent_version`, `os_name`, `os_release`, `arch` alongside the existing fields. |
| F10 | The UI removes manual hardware-entry fields. The "Register cluster" wizard asks the operator to pick the GPU vendor, shows the `curl … /api/agents/install.sh | … bash` one-liner (carrying a pre-generated agent token and the chosen `VF_VENDOR`), then asks only for name + host + port + kind. |
| F11 | The agent is published as three vendor images (`visionforge/agent:{nvidia,rocm,cpu}`) built from `Dockerfile.{nvidia,rocm,cpu}`. The platform hosts a parameterised installer at `GET /api/agents/install.sh` (unauthenticated) that selects the image and GPU flags from `VF_VENDOR`. |

## Out of Scope (Documented)

- Manual cluster entry is **removed** from both API and UI. Air-gapped sites that cannot reach the agent over HTTP are not supported in v1.
- The agent assumes Docker, a Linux host, and (optionally) NVIDIA CUDA or AMD ROCm drivers preinstalled.
- The platform's Redis must be reachable from the worker (private network / VPN).

## Acceptance Criteria

1. `python -m vf_agent.discover` prints valid JSON containing CPU cores, disk total, and OS info.
2. Agent unit tests pass: `pytest agent/tests/` (8 tests covering server auth, /info shape, adopt persistence, heartbeat payload, transport error handling).
3. Backend cluster unit + integration tests pass: 12 unit tests + 7 integration tests, including a stubbed end-to-end that asserts training jobs route to `cluster.{cluster_id}` and the cluster transitions to `busy`.
4. The UI wizard at `/clusters/new` collects only name + host + port + kind; submitting it against a stub agent shows the discovered hardware in the success page.
5. `docker build -t visionforge/agent:cpu -f agent/Dockerfile.cpu .` (and the `nvidia` / `rocm` variants on a suitable host) succeeds and produces an image that includes torch, ultralytics, onnxruntime, psutil, and pynvml.
6. `GET /api/agents/install.sh` returns a shell script (`text/x-shellscript`) whose vendor branch selects the matching image and GPU flags; piping it with `VF_VENDOR=rocm` against an NVIDIA agent is rejected at discovery with `[reason=vendor_mismatch]`.
