#!/usr/bin/env bash
# ------------------------------------------------------------------
# start-lti-dev.sh — Convenience launcher for LTI development
#
# Starts Docker (Postgres + Redis), the FastAPI API server, the
# Next.js frontend, and optionally ngrok.
#
# Usage:
#   ./tools/scripts/start-lti-dev.sh            # without ngrok
#   ./tools/scripts/start-lti-dev.sh --ngrok    # with ngrok tunnel
# ------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[lti-dev]${NC} $*"; }
warn()  { echo -e "${YELLOW}[lti-dev]${NC} $*"; }
error() { echo -e "${RED}[lti-dev]${NC} $*"; }

USE_NGROK=false
if [[ "${1:-}" == "--ngrok" ]]; then
  USE_NGROK=true
fi

# ---- 1. Docker (Postgres + Redis) --------------------------------
info "Starting Docker services (Postgres + Redis)..."
docker compose up -d postgres redis
sleep 2

# Wait for Postgres
for i in {1..10}; do
  if docker compose exec postgres pg_isready -q 2>/dev/null; then
    info "Postgres ready"
    break
  fi
  sleep 1
done

# Wait for Redis
for i in {1..10}; do
  if docker compose exec redis redis-cli ping 2>/dev/null | grep -q PONG; then
    info "Redis ready"
    break
  fi
  sleep 1
done

# ---- 2. Run migrations -------------------------------------------
info "Running database migrations..."
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head

# ---- 3. Start API server (background) ----------------------------
info "Starting API server on :8000..."
export LTI_REDIS_URL="redis://localhost:6379/0"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev}"

uv run uvicorn api.app:app \
  --host 0.0.0.0 --port 8000 --reload \
  --app-dir services/api-server/src &
API_PID=$!
sleep 2

# ---- 4. Start Next.js frontend (background) ----------------------
info "Starting Next.js frontend on :3000..."
(cd apps/web && npm run dev) &
NEXT_PID=$!
sleep 3

# ---- 5. Optionally start ngrok -----------------------------------
NGROK_PID=""
if $USE_NGROK; then
  if ! command -v ngrok &>/dev/null; then
    error "ngrok not found. Install from https://ngrok.com/download"
    exit 1
  fi

  NGROK_DOMAIN="${NGROK_DOMAIN:-}"
  if [[ -n "$NGROK_DOMAIN" ]]; then
    info "Starting ngrok tunnel to :3000 (domain: $NGROK_DOMAIN)..."
    ngrok http 3000 --domain="$NGROK_DOMAIN" &
  else
    info "Starting ngrok tunnel to :3000..."
    ngrok http 3000 &
  fi
  NGROK_PID=$!
  sleep 2
  info "ngrok dashboard: http://127.0.0.1:4040"
fi

# ---- Summary ------------------------------------------------------
echo ""
info "========================================="
info "  LTI dev environment is running"
info "========================================="
info "  API server:  http://localhost:8000"
info "  Frontend:    http://localhost:3000"
info "  Health:      http://localhost:8000/health"
info "  JWKS:        http://localhost:8000/lti/jwks"
if $USE_NGROK; then
  info "  ngrok:       http://127.0.0.1:4040"
fi
info ""
info "  Press Ctrl+C to stop all services"
info "========================================="

# ---- Cleanup on exit ---------------------------------------------
cleanup() {
  info "Shutting down..."
  kill "$API_PID" 2>/dev/null || true
  kill "$NEXT_PID" 2>/dev/null || true
  [[ -n "$NGROK_PID" ]] && kill "$NGROK_PID" 2>/dev/null || true
  info "Done."
}
trap cleanup EXIT INT TERM

# Wait for any background process to exit
wait
