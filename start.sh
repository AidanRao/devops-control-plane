#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[start.sh] %s\n' "$*"
}

die() {
  printf '[start.sh] ERROR: %s\n' "$*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  die "python3 not found. Please install Python 3.11+ and retry."
fi

if [[ ! -f "requirements.txt" ]]; then
  die "requirements.txt not found in repo root."
fi

if [[ ! -d ".venv" ]]; then
  log "Creating virtualenv at .venv ..."
  python3 -m venv .venv
else
  log "Using existing virtualenv at .venv"
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

log "Installing dependencies ..."
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r requirements.txt

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    log "Creating .env from .env.example (will not overwrite an existing .env)"
    cp ".env.example" ".env"
  else
    log "No .env or .env.example found. Continuing without .env."
  fi
fi

# Load env vars (PORT, tokens, etc.) into current process.
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

PORT="${PORT:-8000}"

# 构建前端（Vue 项目），产物输出到 app/static/
if [[ -d "frontend" ]]; then
  if command -v npm >/dev/null 2>&1; then
    pushd frontend >/dev/null
    if [[ ! -d "node_modules" ]]; then
      log "Installing frontend dependencies ..."
      npm install --no-audit --no-fund --loglevel=error
    fi
    log "Building frontend to app/static ..."
    npm run build
    popd >/dev/null
  else
    log "npm not found, skip frontend build (将使用 app/static 下已有的构建产物)"
  fi
fi

log "Starting server on http://127.0.0.1:${PORT}/ui"
exec python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT}"
