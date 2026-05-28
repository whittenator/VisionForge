# Plan: Cluster Discovery & Agent Runtime

## Phases

| # | Phase | Outputs |
|---|---|---|
| 1 | Agent runtime | `agent/` package, Dockerfile, supervisor entrypoint, hardware probe, HTTP server, heartbeat loop |
| 2 | Backend discovery | `POST /api/clusters/discover`, schema columns + Alembic migration, `AgentUnreachableError`, removal of manual entry |
| 3 | Frontend wizard | Rewritten `/clusters/new` (token generated client-side, hardware fields removed); `/clusters` shows OS + agent version |
| 4 | E2E proof | Stubbed integration test asserts Celery routing to `cluster.{id}` and the busy→online lifecycle |
| 5 | Hardening | Token rotation endpoint + test; agent version field in `/info` |
| 6 | Documentation | CLAUDE.md, README.md, this spec |

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Discovery direction | Backend pulls from agent | Operator-stated requirement; avoids needing operators to type specs |
| Job transport | Celery + Redis (push) | Matches existing wiring; operators with no platform-side changes |
| Manual entry | Removed entirely | User decision (see questions in branch history); reduces UI complexity |
| TLS | Plain HTTP for v1 | Agents are expected on private networks; `scheme=https` is supported but not certificate-managed by the platform |
| Token lifecycle | Operator-supplied agent token persists across restarts; platform-issued register token rotatable on demand | Two-token design isolates the agent's bootstrap identity from its platform-issued session identity |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Agent on NAT'd network unreachable from platform | Document the private-network requirement; future work: HTTP long-poll fallback (out of scope for v1) |
| Agent image grows large (includes torch/cuda) | Backend image already has the same deps; agent image extends it — no duplicate ML stack to maintain |
| `register_token` leaks | `POST /rotate-token` invalidates the old token and forces re-adoption |
| Operator mistypes the agent token | `[reason=auth]` returned in 502 detail; UI surfaces "agent rejected the token" |

## Test Strategy

- **Agent**: `agent/tests/` — `pytest` against `httpx.MockTransport`; no Docker required.
- **Backend service**: `backend/tests/unit/test_cluster_service.py` — pure SQLite + `httpx.MockTransport`.
- **Backend API**: `backend/tests/integration/test_clusters_api.py` — FastAPI `TestClient` with `monkeypatch` on `cluster_service.httpx.Client`.
- **Canonical proof**: `test_train_with_available_cluster_routes_to_cluster_queue` asserts both queue name and cluster `busy` state after discover→heartbeat→train.
