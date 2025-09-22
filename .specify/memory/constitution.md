<!--
Sync Impact Report
Version change: 1.0.0 → 1.1.0
Modified principles: None
Added sections: Quick Visual Check (required for frontend work)
Removed sections: None
Templates requiring updates:
	✅ Reviewed: .specify/templates/plan-template.md (no changes needed)
	✅ Reviewed: .specify/templates/spec-template.md (no changes needed)
	✅ Reviewed: .specify/templates/tasks-template.md (no changes needed)
Follow-up TODOs:
	- TODO(RATIFICATION_DATE): Confirm original adoption date if different from first commit.
-->

# VisionForge Constitution

## Core Principles

### I. Code Quality Discipline (NON-NEGOTIABLE)
All code MUST meet baseline quality gates before merge:
- Static analysis clean: no errors, and no new warnings without justification.
- Formatting enforced via autoformatter; consistent code style per language.
- Strong typing where available (TypeScript, Python typing, etc.). Public APIs fully typed.
- Small, cohesive changes: single-responsibility PRs, <= 400 lines diff when practical.
- No dead code, commented-out blocks, or unused dependencies.
Rationale: High signal-to-noise reviews and maintainable code reduce defects and cycle time.

### II. Tests-First & Test Completeness
New behavior MUST be introduced via failing tests first. Minimum coverage expectations:
- Unit tests for pure logic; contract tests for APIs/CLIs; integration tests for workflows.
- P0 paths covered; critical error paths asserted; schema and I/O contracts snapshot-tested.
- Coverage targets: ≥ 80% statements/branches for new/changed files unless justified.
- Tests execute in CI fast path (< 10 minutes full suite; < 2 minutes diff-based subset).
Rationale: TDD and comprehensive checks prevent regressions and document intent.

### III. Consistent User Experience
UI/CLI surfaces MUST use shared patterns and be accessible:
- Design tokens and shared components required; no ad-hoc styling.
- UX states standardized: loading, empty, error, success.
- Accessibility: WCAG 2.1 AA conformance for UI; CLI uses readable text + JSON, clear exit codes.
- Copy and terminology centralized; user-facing strings live in a single source.
Rationale: Consistency improves learnability and reduces user errors across the platform.

### IV. Performance & Efficiency Budgets
Each feature MUST declare and meet explicit performance budgets:
- Latency targets per operation (e.g., p95 < 200ms API, < 100ms UI interactions) unless domain-justified.
- Training/export pipelines publish throughput and resource profiles; ONNX export validated.
- Performance tests and regression guards added for hot paths; monitoring hooks wired.
- Reasonable resource use: avoid N^2 operations on large datasets; backpressure, batching, and streaming where applicable.
Rationale: Performance is a feature; predictable latency and efficiency keep teams fast.

## Quality Gates & Workflow

All PRs MUST include:
- Constitution checklist acknowledgment (quality, tests, UX, performance).
- Linked issue/feature spec and scope boundaries.
- Evidence: test diffs/screens, perf numbers or plans for perf validation.

CI MUST enforce:
- Lint/format/type checks.
- Test suite pass with coverage report and contract snapshot verification.
- Optional: allow temporary waivers with issue-linked justification and expiry.

## Quick Visual Check (required for frontend work)

For any frontend change (components, pages, styles, routing), the contributor MUST execute
an automated visual and behavior verification using the Playwright MCP integration:

1. Identify modified components/pages.
2. Navigate to each affected route with `mcp__playwright__browser_navigate`.
3. Validate behaviour against spec requirements and acceptance criteria.
4. Capture full-page screenshots (desktop 1440px) via Playwright MCP.
5. Inspect console output with `mcp__playwright__browser_console_messages` for regressions.

Evidence (screenshots, notes, and console logs) MUST be attached to the PR description.
If automated navigation is not feasible for a route, document why and provide a manual
reproduction path. Visual checks are part of the Definition of Done for frontend tasks.

## Governance

- This Constitution supersedes other style guides where in conflict for VisionForge.
- Amendment process: propose PR with redline diff and migration notes; require 2 approvals
	from maintainers, 1 from UX or product, and 1 from a platform/infra owner for perf-impacting changes.
- Versioning policy: semantic versioning of the Constitution.
	• MAJOR: Backward-incompatible governance changes or removal/redefinition of principles.
	• MINOR: New principle/section or material expansion of guidance.
	• PATCH: Clarifications, non-semantic wording, typo fixes.
- Compliance review: quarterly audit of 5 recent PRs per area (backend, frontend, ML) for adherence.

**Version**: 1.1.0 | **Ratified**: TODO(RATIFICATION_DATE): First adoption date not recorded | **Last Amended**: 2025-09-21