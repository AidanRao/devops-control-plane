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

if ! command -v conda >/dev/null 2>&1; then
  die "conda not found. Please install Anaconda/Miniconda and retry."
fi

if [[ ! -f "requirements.txt" ]]; then
  die "requirements.txt not found in repo root."
fi

CONDA_ENV_NAME="devops-control-plane"

if ! conda env list | grep -q "^$CONDA_ENV_NAME\s"; then
  log "Creating conda environment $CONDA_ENV_NAME with Python 3.11 ..."
  conda create -n "$CONDA_ENV_NAME" python=3.11 -y
else
  log "Using existing conda environment $CONDA_ENV_NAME"
fi

log "Activating conda environment $CONDA_ENV_NAME ..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV_NAME"

log "Installing dependencies ..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    log "Creating .env from .env.example (will not overwrite an existing .env)"
    cp ".env.example" ".env"
  else
    log "No .env or .env.example found. Continuing without .env."
  fi
fi

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

PORT="${PORT:-8000}"

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
exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT}"
