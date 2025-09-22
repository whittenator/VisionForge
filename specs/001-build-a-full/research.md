# Research: VisionForge MVP

Date: 2025-09-21
Feature: Build a full-stack Computer Vision Platform (MVP)

## Unknowns & Decisions

1) Job orchestration library
- Unknown: The prompt specifies "Celter". Likely intended: Celery.
- Decision: Use Celery (Python) with Redis broker for MVP; leave pluggable for future.
- Rationale: Mature ecosystem, FastAPI integration, wide deployment guides.
- Alternatives: RQ, Dramatiq, Arq, Kubernetes jobs (future), Ray (heavier).

2) Authentication
- Unknown: Method (SSO/OAuth/email+password?)
- Decision: MVP: Superuser auto-created at backend startup; admin UI to create users/assign roles. No self-registration.
- Rationale: Meets MVP need with minimal surface; future SSO possible.
- Alternatives: OAuth/OIDC (Auth0/Keycloak), SAML for enterprise.

3) Dataset scale & concurrency targets
- Unknown: Max items and concurrent users.
- Decision: MVP target: up to 1M assets; 10–50 concurrent annotators.
- Rationale: Sets perf envelopes and data model constraints.
- Alternatives: Scale via sharding/object store partitioning later.

4) Training hardware / accelerators
- Unknown: Standard GPU targets.
- Decision: NVIDIA GPUs (CUDA) for MVP; CPU fallback supported but slow.
- Rationale: Ultralytics commonly targets CUDA.
- Alternatives: ROCm/AMD later; ONNXRuntime with DirectML for Windows.

5) ONNX export validation
- Unknown: Tolerance and validation approach.
- Decision: Compare ONNX inference vs PyTorch on validation subset; require metrics within 1% absolute (classification) or mAP-50 within 1–2 points (detection).
- Rationale: Ensures deployable parity.
- Alternatives: Operator-by-operator unit tests (heavier).

6) Active Learning strategies (MVP scope)
- Decision: Implement uncertainty (entropy) and diversity (k-means on embeddings) first; hybrid as composition.
- Rationale: Common, effective baseline.
- Alternatives: Core-set, BALD, margin sampling.

7) Embeddings generation
- Decision: Use OpenCLIP(pip install open_clip_torch) and the hugging face model DatologyAI/retr-opt-vit-b-32 for image embeddings; store vectors in pgvector. 
- Rationale: Supports diversity sampling and search.

8) Observability & structured logging
- Decision: JSON logging everywhere; Prometheus metrics endpoints for API and workers; Grafana dashboards for ingest, training, export, AL queue throughput.

9) Frontend component library
- Decision: shadcn/ui over Tailwind primitives; shared tokens and components; a11y-first patterns.

10) Data retention
- Unknown: Retention period.
- Decision: No automatic deletion in MVP; admin-managed cleanup.
- Alternatives: Configurable retention per project later.

## Alternatives Considered (high-level)
- Monorepo vs multi-repo: Monorepo MVP for ease of orchestration.
- GraphQL vs REST: REST (FastAPI) with OpenAPI; consider GraphQL later for complex queries.
- Direct FS storage vs MinIO: MinIO (S3) chosen for portability and cloud parity.

## Risks & Mitigations
- Large video handling → Use server-side frame extraction with chunking and backpressure; streaming uploads.
- Label quality drift → Review workflows, per-annotator metrics, and taxonomy constraints.
- Cost of training → Make training modular with sensible defaults; allow smaller subsets.

## Open Questions
- SSO/OIDC timeline?
- Multi-tenant isolation requirements?
- Desired model zoo beyond Ultralytics?
