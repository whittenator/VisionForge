
# Implementation Plan: VisionForge Web Revamp

**Branch**: `003-visionforge-web-revamp` | **Date**: 2025-09-22 | **Spec**: `/home/twhitten/copilot/VisionForge/specs/003-visionforge-web-revamp/spec.md`
**Input**: Feature specification from `/specs/003-visionforge-web-revamp/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Deliver a cohesive, modern web UX for VisionForge across navigation, auth, datasets, annotation, experiments, artifacts, and admin—eliminating duplicated headers, accelerating time-to-value, and enabling team collaboration with clear roles and auditability. Technical implementation will leverage the existing stack (FastAPI + SQLAlchemy/Alembic on Python 3.11; React 19 + Vite + Tailwind CSS 4) with PostgreSQL (pgvector-enabled) as the primary datastore and Playwright-driven visual checks for frontend QA. Contracts and entities are defined below to guide a tests-first delivery.

## Technical Context
**Language/Version**: Backend: Python 3.11; Frontend: JavaScript (React 19), Node.js 20.x  
**Primary Dependencies**: Backend: FastAPI, Uvicorn, SQLAlchemy, Alembic; Frontend: React, react-router-dom, Tailwind CSS 4, Vite  
**Storage**: PostgreSQL (pgvector enabled) for prod; SQLite for local/dev convenience  
**Testing**: pytest (unit/integration/contract), Playwright for frontend visual/behavior checks  
**Target Platform**: Linux servers (Docker/Kubernetes deploy), local dev on Linux/macOS  
**Project Type**: web (frontend + backend detected)  
**Performance Goals**: UI: key screens interactive < 1.5s; annotation actions < 100ms; API p95 < 200ms for standard operations  
**Constraints**: WCAG 2.1 AA; single global header enforced; resumable uploads; secure auth; provenance and audit logging  
**Scale/Scope**: Datasets up to 100k assets (target); concurrent uploads 5–10 sessions per workspace (initial); multi-member projects

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The design MUST satisfy these gates derived from the project Constitution:

- Code Quality: Linting/formatting configured; static typing enabled; no dead code; small, cohesive changes.
- Testing: Tests-first for new work; unit + contract + integration tests planned; coverage goals defined.
- UX Consistency: Uses shared design system/components; WCAG 2.1 AA acceptance; consistent empty/loading/error states.
- Performance: Explicit budgets per feature; plan includes perf tests and monitoring; no known regressions vs. baseline.

Initial Constitution Assessment (Pre-Phase 0):
- Code Quality: PASS — existing linters/formatters; we’ll maintain typing and small PRs.
- Testing: PASS — tests-first approach with contract/integration tests keyed to new contracts.
- UX Consistency: PASS — shared layout shell, design tokens, consistent states; Playwright visual checks.
- Performance: PASS — budgets declared above; perf guards to be added for hot paths (uploads, annotation ops).

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 2 — Web application (frontend + backend already present)

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

Unknowns and Resolutions (from spec NEEDS CLARIFICATION):
- MFA/SSO scope and providers (Phase 2 roadmap) → Decision: Defer MFA and SSO to Phase 2; prioritize OIDC (Google) and SAML (Okta) as first providers; ensure auth architecture remains provider-agnostic.
- Max dataset size, file formats, and concurrent uploads → Decision: Target 100k assets/dataset at GA with common image formats (JPEG, PNG) and ZIP ingestion; support concurrent uploads up to 10 sessions/workspace, configurable.
- Model evaluation visuals at GA → Decision: Include confusion matrix and per-class metrics at GA; PR curves post-GA.
- Multi-workspace availability at GA → Decision: Post-GA; include workspace switcher scaffolding hidden behind a flag.
- Data residency/region requirements → Decision: Offer US (default) with EU as optional region post-GA; document constraints; store region metadata at workspace level.

Research tasks executed and consolidated into research.md (see file for details). All unknowns are resolved for planning with provisional decisions and revisit notes.

Output: research.md with decisions and rationales

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts (planned):
   - One test file per endpoint (to be added during implementation tasks)
   - Assert request/response schemas
   - Initially failing until implementation catches up

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh copilot`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/* (OpenAPI skeleton), quickstart.md, agent-specific file updated

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before UI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [ ] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [ ] Complexity deviations documented

---
*Based on the project Constitution — see `.specify/memory/constitution.md`*
