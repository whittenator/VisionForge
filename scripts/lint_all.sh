#!/usr/bin/env bash
set -euo pipefail

echo "== Frontend: ESLint =="
pushd frontend >/dev/null
npm run lint || true
popd >/dev/null

echo "== Backend: Ruff =="
if command -v ruff >/dev/null 2>&1; then
  ruff check backend/src backend/tests || true
else
  echo "ruff not found. Install with: python -m pip install -r backend/requirements-dev.txt" >&2
fi

echo "== Backend: Black --check =="
if command -v black >/dev/null 2>&1; then
  black --check backend/src backend/tests || true
else
  echo "black not found. Install with: python -m pip install -r backend/requirements-dev.txt" >&2
fi

echo "Linting complete."
