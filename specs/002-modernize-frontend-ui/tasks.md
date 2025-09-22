# Tasks: Modernize Frontend UI, Add Login Gate, and Fix Backend Docker Import Error

Feature Dir: /home/twhitten/copilot/VisionForge/specs/002-modernize-frontend-ui
Plan: /home/twhitten/copilot/VisionForge/specs/002-modernize-frontend-ui/plan.md
Contracts: /home/twhitten/copilot/VisionForge/specs/002-modernize-frontend-ui/contracts/openapi.yaml

Notes:
- [P] means tasks can be executed in parallel with other [P] tasks.
- Follow TDD: add/execute tests before implementing behavior.
- Keep PRs small and scoped; run linters/formatters.

## Setup & Quality Gates

- [X] T001. Ensure docker-compose backend import fix strategy documented in research is codified (no implementation yet)
- Files: /home/twhitten/copilot/VisionForge/specs/002-modernize-frontend-ui/research.md
- Notes: Confirm we’ll set PYTHONPATH or change uvicorn target path; proceed to tests next.

- T002. Add minimal auth contract tests (failing) for /auth/login and /auth/logout
- Files: backend/tests/contract/test_auth_contract.py
- Content: Use Schemathesis or httpx to assert contract in contracts/openapi.yaml
- Dependencies: Contracts file

- T003. Add frontend integration tests (failing) for login flow and route guard [P]
- Files: frontend/tests/integration/auth_flow.spec.ts
- Content: Playwright: unauthenticated redirect to /login; valid login redirects to /; logout returns to /login.
- Dependencies: Plan + Quickstart

- T004. Add frontend visual tests (failing) for login and homepage [P]
- Files: frontend/tests/visual/auth_visual.spec.ts
- Content: Capture screenshots at 1440px; assert no major diffs; check console logs for errors.
- Dependencies: Constitution visual check

## Backend: Compose Fix & Auth Endpoints

T005. Fix backend compose import error (one of):
- Option A: Add `ENV PYTHONPATH=/app/src` to backend/Dockerfile
- Option B: Change uvicorn target to `src.app.main:app` in Dockerfile and docker-compose.yml
- Files: backend/Dockerfile, docker-compose.yml
- Dependencies: T001
  
- [X] Applied: Set ENV PYTHONPATH=/app/src in backend/Dockerfile

T006. Add backend auth router skeleton to satisfy contracts (no real auth yet)
- Files: backend/src/app/api/auth.py, backend/src/app/main.py (include_router)
- Endpoints: POST /auth/login, POST /auth/logout with stub behavior and appropriate status codes
- Dependencies: T002
  
- [X] Added: backend/src/app/api/auth.py and included router in main.py

T007. Implement basic email/password auth (MVP) and session handling
- Files: backend/src/app/services/auth.py, backend/src/app/models/user.py (if needed), backend/src/app/api/auth.py
- Behavior: Validate credentials (hardcoded or simple store for MVP), return token in 200; logout returns 204.
- Dependencies: T006
  
- [X] Implemented: backend/src/app/services/auth.py and refactored API to use it

T008. Add backend tests for auth service and API integration
- Files: backend/tests/unit/test_services_auth.py, backend/tests/integration/test_auth_api.py
- Content: Happy path + invalid credentials; health unaffected.
- Dependencies: T007
  
- [X] Added: backend/tests/unit/test_services_auth.py and backend/tests/integration/test_auth_api.py

## Frontend: UI, Routing, and Auth Flow

T009. Add auth API client and types [P]
- Files: frontend/src/services/auth.js (or .ts), frontend/src/lib/types.ts
- Content: login(email, password) → { token, user }; logout() → void
- Dependencies: Contracts
  
- [X] Added: frontend/src/services/api.ts, frontend/src/services/auth.ts

T010. Add global auth state (context/store) [P]
- Files: frontend/src/services/auth-store.js (or context), wire in `App.jsx`
- Content: store token/user; persist in memory for MVP; expose login/logout
- Dependencies: T009
  
- [X] Added: frontend/src/services/auth-store.tsx

T011. Add login page and form [P]
- Files: frontend/src/pages/auth/Login.jsx, route in `App.jsx`
- Content: modern, accessible form; error/loading states; submit calls API
- Dependencies: T009, T010
  
- [X] Added: frontend/src/pages/auth/Login.jsx

T012. Add route guard to protect homepage and primary routes
- Files: frontend/src/components/layout/ProtectedRoute.jsx, update `App.jsx` routes
- Behavior: if not authenticated → redirect to /login; remember intended path
- Dependencies: T010
  
- [X] Added: frontend/src/components/layout/ProtectedRoute.tsx; wrapped protected routes

T013. Modernize base layout and styles for full-viewport responsive design
- Files: frontend/src/components/layout/Shell.jsx, frontend/src/styles/globals.css
- Content: responsive container, typography scale, spacing tokens; ensure pages fill height
- Dependencies: none (can be done in parallel with T011/T012) [P]
  
- [X] Updated: AppShell header and layout; pages now fill viewport via min-h classes

T014. Update homepage to use modern layout and ensure responsiveness
- Files: frontend/src/pages/projects/index.jsx (or current homepage), shared components if needed
- Dependencies: T013, T012

## Observability, Accessibility, and Polish

T015. Add accessible states and ARIA for login and nav components [P]
- Files: frontend/src/pages/auth/Login.jsx, nav components
- Dependencies: T011

T016. Add auth metrics/logs on backend
- Files: backend/src/app/observability/metrics.py (or auth module), auth endpoints
- Content: counters for login_success/login_failure; structured logs
- Dependencies: T007

T017. Update quickstart and docs
- Files: /home/twhitten/copilot/VisionForge/specs/002-modernize-frontend-ui/quickstart.md, README.md (if necessary)
- Dependencies: After major behavior is stable

## Parallel Execution Guidance
- Group 1 [P]: T003, T004 (frontend tests), T009 (API client), T013 (layout)
- Group 2 [P]: T010 (auth store), T011 (login page)
- Group 3 [P]: T015 (a11y polish) after T011

## Task Agent Commands (examples)
- Run backend contract tests: pytest -q backend/tests/contract/test_auth_contract.py
- Run frontend Playwright tests: npm --prefix frontend run test:ui
- Build backend container: docker compose build backend

