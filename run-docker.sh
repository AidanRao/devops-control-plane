#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="devops-cp:latest"
CONTAINER_NAME="devops-cp"
HOST_PORT="8000"
CONTAINER_PORT="8000"

log() {
  printf '[run-docker.sh] %s\n' "$*"
}

die() {
  printf '[run-docker.sh] ERROR: %s\n' "$*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  die "docker not found. Please install Docker Desktop and retry."
fi

log "Building image: ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" -f Dockerfile .

if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  log "Removing existing container: ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

ENV_ARGS=()
if [[ -f ".env" ]]; then
  ENV_ARGS+=(--env-file ".env")
fi

log "Starting container: ${CONTAINER_NAME} (port ${HOST_PORT}:${CONTAINER_PORT})"
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  "${ENV_ARGS[@]}" \
  "${IMAGE_TAG}" >/dev/null

log "Running: http://127.0.0.1:${HOST_PORT}/ui"
log "Logs:    docker logs -f ${CONTAINER_NAME}"
log "Stop:    docker stop ${CONTAINER_NAME}"
log "Remove:  docker rm -f ${CONTAINER_NAME}"
