# Quickstart — VisionForge Web Revamp

This quickstart validates the core user journey using contracts and test scaffolding.

## Prerequisites
- Backend dev env: Python 3.11, FastAPI, SQLAlchemy, Alembic
- Frontend dev env: Node.js 20.x, React 19, Vite, Tailwind CSS 4
- Database: PostgreSQL (dev) or SQLite (local)

## Steps
1. Start backend API and DB.
2. Create account via /auth/signup (201).
3. Login via /auth/login (200); store session token.
4. Create a Project; list Projects (200 with created project).
5. Create a Dataset under the Project (201).
6. Initiate an Upload session for the Dataset (202); upload files; verify per-file and batch progress.
7. Open labeling workspace; create an annotation using keyboard shortcuts; verify autosave.
8. Trigger a training run; check run status until succeeded/failed; open run detail to view parameters/metrics.
9. Promote to model and export; confirm artifact exists with checksum and size; download succeeds.
10. Invite a user; accept invite; verify role-based UI states and audit log entry.

## Visual & Behavior Checks (Frontend)
- Single global header present on all routes; no duplicates.
- Empty states for Projects/Datasets/Experiments/Artifacts show appropriate primary CTAs.
- URL-persisted filters restore on reload.

## Cleanup
- Archive the test project and delete test data.
