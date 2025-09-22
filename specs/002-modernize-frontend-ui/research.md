# Research: Modernize UI, Add Login Gate, Fix Backend Docker Import

## Unknowns and Decisions

1. Authentication Method
- Unknown: Local email/password vs OAuth/SSO (e.g., GitHub/Google) vs existing identity provider.
- Decision (provisional): Implement local email/password for MVP, abstractable to add OAuth later.
- Rationale: Unblocks gated homepage quickly; aligns with immediate need; can be upgraded.
- Alternatives: OAuth-only, SSO via enterprise IdP.

2. Session Duration and Renewal
- Unknown: Exact timeout and Remember Me behavior.
- Decision (provisional): Default 8-hour session; no persistent Remember Me for MVP; auto-logout on expiry; refresh on activity.
- Rationale: Reasonable default for dev/test; configurable later.
- Alternatives: Short-lived tokens with refresh, sliding window, persistent login.

3. Authenticated user visiting /login
- Unknown: Redirect vs show state.
- Decision: Redirect to homepage.
- Rationale: Common pattern, fewer edge cases.

4. Observability for Auth
- Unknown: Exact metrics/events.
- Decision: Log success/failure events and expose counters via Prometheus tags.
- Rationale: Minimal but useful telemetry.

5. Backend Docker Import Error
- Observation: Dockerfile runs `uvicorn app.main:app` but WORKDIR /app and sources under /app/src; PYTHONPATH not set; pip install . may not install package if project not configured.
- Decision: Add `ENV PYTHONPATH=/app/src` and/or invoke `uvicorn src.app.main:app` OR refactor to editable install.
- Rationale: Ensures `import app` resolves; minimal change to unblock compose.
- Alternatives: Install package properly via `pip install -e .` with setup; adjust module entry.

## Best Practices Notes
- Frontend: Use route guards with react-router; maintain auth state in context; handle loading and error states; apply Tailwind design tokens.
- Accessibility: Contrast, focus states, semantic markup; keyboard navigation for forms.
- Security: Avoid verbose error messages on auth failure; rate-limit attempts (future); CSRF/state concerns if using cookies (future decision based on mechanism).

## Outcome
These decisions unblock Phase 1 design and contracts. Open items will be revalidated with stakeholders.
