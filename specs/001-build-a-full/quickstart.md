# Quickstart: VisionForge MVP

This guide exercises the MVP flow end-to-end.

## Prerequisites
- Docker & docker-compose
- .env with Postgres, MinIO, Redis, and app secrets

## Steps
1) Start stack (containers)
	- From repo root:
	  - docker-compose up -d --build
	- Visit backend: http://localhost:8000/health
	- Visit frontend: http://localhost:5173/

2) Local dev (optional)
	- Backend (hot reload):
	  - cd backend
	  - uvicorn app.main:app --reload --port 8000
	- Frontend (Vite):
	  - cd frontend
	  - npm install
	  - npm run dev

3) Login as superuser and open Admin
	- SUPERUSER_EMAIL/PASSWORD from .env.example

4) Create a project and dataset; upload sample images/videos

5) Create a dataset version snapshot

6) Annotate: draw boxes (detection) or set tags (classification)

7) Launch training (choose task and defaults)

8) Monitor job logs and metrics dashboard
	- Prometheus: http://localhost:9090
	- Grafana: http://localhost:3000 (admin creds from .env.example)

9) Export to ONNX and validate

10) Promote artifact to Staging/Production

## Quick Visual Check (required)
Run the lightweight UI visual sweep to capture baseline screenshots and console logs.

- cd frontend
- npm run test:ui -- tests/visual/visual-check.spec.ts --project=chromium
- Artifacts: frontend/test-results/visual/*.png and *.console.log

## Notes
- If ports 5173/5174 are busy, Vite may pick the next available port.
- For CI, ensure pytest and Playwright browsers are installed to run perf and visual suites.
