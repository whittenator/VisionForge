# Tasks: Cluster Discovery & Agent Runtime

Each task lists a **verifiable output** — a concrete observation that proves it's done.

## Phase 1: Agent runtime

- [X] **T001** `agent/Dockerfile`, `agent/requirements.txt`, `agent/src/vf_agent/`.
  *Verify:* directory exists; `agent/Dockerfile` references `python:3.11-slim` and copies both `backend/` and `agent/`.
- [X] **T002** `vf_agent/discover.py`: hardware + OS probe via psutil / pynvml / rocm-smi / platform.
  *Verify:* `PYTHONPATH=agent/src python -m vf_agent.discover` prints JSON with `cpu_cores`, `disk_total_gb`, `gpu_vendor`, `os.{name,release,arch}`.
- [X] **T003** `vf_agent/server.py`: FastAPI app with `/health` (no auth), `/info`, `/telemetry`, `/adopt` (bearer auth).
  *Verify:* `pytest agent/tests/test_server.py` — 6 cases including 401 on bad token and 503 when `VF_AGENT_TOKEN` is unset.
- [X] **T004** `vf_agent/heartbeat.py`: posts telemetry to the platform every `VF_AGENT_HEARTBEAT_INTERVAL` seconds.
  *Verify:* `pytest agent/tests/test_heartbeat.py` — payload includes `register_token` and `status=online`; transport error returns code 0.
- [X] **T005** `vf_agent/main.py`: supervisor that starts the HTTP server, waits for `identity.json`, then spawns the Celery worker bound to `cluster.{cluster_id}`.
  *Verify:* `python -m vf_agent.main` aborts with exit code 2 when `VF_AGENT_TOKEN` is unset; otherwise launches uvicorn on port 9443 and blocks for identity.

## Phase 2: Backend discovery endpoint

- [X] **T006** New columns on `clusters`: `agent_host`, `agent_port`, `agent_version`, `os_name`, `os_release`, `arch`. Alembic revision `0004_cluster_discovery`.
  *Verify:* migration file exists; `discover_cluster` test asserts these columns are populated from `/info`.
- [X] **T007** `POST /api/clusters/discover` calls agent `/info` + `/adopt`, creates a `Cluster` row pre-populated from discovery.
  *Verify:* `test_discover_probes_agent_and_creates_cluster` — Cluster row has `cpu_cores=32`, `gpu_count=2`, `agent_host`, `os_name="Linux"`.
- [X] **T008** Remove `POST /api/clusters` (manual entry).
  *Verify:* `router.routes` includes `/discover` but not the bare `POST /api/clusters`.
- [X] **T009** `AgentUnreachableError` → 502 with `[reason=connect|timeout|auth|bad_response]`.
  *Verify:* `test_discover_502s_when_agent_unreachable` — body contains `[reason=connect]`.

## Phase 3: Frontend wizard

- [X] **T010** Rewrite `frontend/src/pages/clusters/new.tsx` to a two-step flow: install command (Step 1) + name/host/port/kind (Step 2).
  *Verify:* the file contains no `cpu_cores`/`ram_total_mb`/`gpu_count` form inputs and submits `POST /api/clusters/discover`.
- [X] **T011** Show discovered specs on the result page (chips for CPU, RAM, disk, GPU, OS, agent version).
  *Verify:* the registered-state JSX renders `<Badge>` chips for each field.
- [X] **T012** `/clusters` index card shows OS and agent endpoint (`agent_host:agent_port · vX.Y.Z`).
  *Verify:* `Cluster` interface includes the new fields and they're rendered in the card footer.

## Phase 4: Stubbed E2E proof

- [X] **T013** `test_train_with_available_cluster_routes_to_cluster_queue` asserts: cluster created via discover → heartbeat received → training launched → `celery_app.send_task` called with `queue=cluster.{cluster_id}` and `args[0].clusterId` set; cluster status flips to `busy` and `active_job_id` populated.
  *Verify:* `pytest backend/tests/integration/test_clusters_api.py -k routes_to_cluster_queue` passes.

## Phase 5: Hardening

- [X] **T014** `POST /api/clusters/{id}/rotate-token` re-issues the register token; old token immediately fails heartbeat.
  *Verify:* `test_rotate_register_token_invalidates_old_token` + `test_rotate_token_invalidates_old_token` integration test pass.
- [X] **T015** `compose.agent.yml` overlay starts the agent on the same Docker network as the platform.
  *Verify:* `docker compose -f docker-compose.yml -f compose.agent.yml config agent` resolves without error.

## Phase 6: Documentation

- [X] **T016** Update `CLAUDE.md` Compute Clusters section to describe the discovery flow and agent endpoints.
- [X] **T017** Update `README.md` to replace lifecycle 1–4 with the discovery flow and add an "Agent quick install" subsection.
- [X] **T018** This spec (`specs/004-cluster-discovery/`).
