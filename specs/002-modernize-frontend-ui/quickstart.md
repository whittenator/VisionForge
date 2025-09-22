# Quickstart: UI Login and Backend Compose

## Prerequisites
- Docker and docker-compose
- Node 18+ for local frontend dev

## Backend (compose)
1. Create `.env` with required variables (POSTGRES_*, MINIO_*, GRAFANA_*). Use sample values for local.
2. Start stack:
   - `docker compose up backend --build`
3. Verify health:
   - Visit http://localhost:8000/health → {"status":"ok"}

## Frontend (dev)
1. From `frontend/`, install deps: `npm install`
2. Start dev server: `npm run dev` (exposed on http://localhost:5173)
3. Navigate to http://localhost:5173 → unauthenticated users should be redirected to /login.

## Login Flow (expected)
- Access /login, submit valid credentials → redirect to homepage.
- Invalid credentials → error message.
- Logout → back to /login.

## Visual and Behavior Checks
- Run Playwright tests: `npm run test:ui`
- Capture screenshots for login and homepage at desktop resolution.
