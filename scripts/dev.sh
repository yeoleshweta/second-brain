#!/usr/bin/env bash
# Start both backend and frontend in dev mode.
# Use Ctrl+C to stop both.
set -e

cd "$(dirname "$0")/.."

cleanup() {
  echo ""
  echo "Stopping..."
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo "→ Starting backend (http://localhost:8000)"
(cd backend && uv run python -m src.api.main) &

echo "→ Starting frontend (http://localhost:5173)"
(cd frontend && npm run dev) &

wait
