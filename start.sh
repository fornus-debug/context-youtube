#!/usr/bin/env bash
# Start backend (FastAPI) + frontend (Next.js) together
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Check .env ──────────────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  echo "ERROR: .env not found. Copy .env.example and set your API key:"
  echo "  cp .env.example .env"
  exit 1
fi

# ── Install frontend deps if needed ─────────────────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[setup] Installing frontend dependencies..."
  cd "$ROOT/frontend" && npm install
fi

# ── Start backend ────────────────────────────────────────────────────────────
echo "[backend] Starting FastAPI on http://localhost:8000 ..."
cd "$ROOT"
uvicorn api:app --port 8000 --reload &
BACKEND_PID=$!

# ── Start frontend ───────────────────────────────────────────────────────────
echo "[frontend] Starting Next.js on http://localhost:3000 ..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

# ── Cleanup on exit ──────────────────────────────────────────────────────────
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

echo ""
echo "  App running at  →  http://localhost:3000"
echo "  API docs        →  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

wait
