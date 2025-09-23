# Research — VisionForge Web Revamp

Date: 2025-09-22
Branch: 003-visionforge-web-revamp

## Decisions and Rationale

1. MFA/SSO Roadmap
- Decision: Defer to Phase 2. Prioritize OIDC (Google) and SAML (Okta).
- Rationale: Addresses enterprise readiness without blocking GA; architecture remains provider-agnostic.
- Alternatives: Build-in-house SSO now (rejected: extends timeline); Password-only (rejected: weak for teams).

2. Dataset Scale & Upload Concurrency
- Decision: Target 100k assets/dataset GA; allow 5–10 concurrent upload sessions/workspace; support JPEG/PNG + ZIP.
- Rationale: Meets typical team needs; manageable infra; resumable uploads and progress visibility are musts.
- Alternatives: Unlimited scale (rejected: risk); 1 session only (rejected: slow onboarding).

3. Model Evaluation Visuals at GA
- Decision: Include confusion matrix and per-class metrics; PR curves post-GA.
- Rationale: Delivers immediate value for classification; avoids scope creep.
- Alternatives: Full suite at GA (rejected: time); none at GA (rejected: gap vs. expectations).

4. Multi-Workspace
- Decision: Post-GA; include hidden scaffolding and a workspace switcher for later activation.
- Rationale: Reduces complexity now; keeps UI IA future-ready.
- Alternatives: GA scope (rejected: adds complexity across auth, perms, filtering).

5. Data Residency/Region
- Decision: US default; EU region post-GA; store workspace.region and enforce data placement policies.
- Rationale: Future compliance needs; preserves optionality without blocking GA.
- Alternatives: Single region only (rejected: limits adoption); Full regional support now (rejected: scope/time).

6. Performance Budgets
- Decision: UI TTI < 1.5s typical datasets; annotation < 100ms; API p95 < 200ms.
- Rationale: Matches product requirements; sets clear perf gates.
- Alternatives: No budgets (rejected: risks regressions).

## Best Practices & Patterns

- Backend: FastAPI + SQLAlchemy session management, Alembic migrations, RBAC middleware, OpenAPI-first contracts, idempotent uploads, background jobs for long-running tasks.
- Frontend: Single app shell, route guards with role checks, Tailwind tokens, skeleton loaders, URL-persisted filters, keyboard-accessible annotation tools.
- Testing: Contract tests from OpenAPI; integration tests for core flows; Playwright visual checks per Constitution.
- Observability: Structured logging, request IDs/trace IDs, metrics for uploads/training/export, job events surfaced to UI notifications.

## Open Questions to Revisit (Post-GA Planning)

- Exact SSO providers sequence; MFA mechanisms (TOTP vs. WebAuthn).
- PR curve visualization details and thresholds.
- Regional data handling enforcement and backups strategy.
