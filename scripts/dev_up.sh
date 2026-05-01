#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_CTL="$ROOT_DIR/scripts/backend_ctl.sh"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_HEALTH_URL="http://127.0.0.1:8000/api/meta"
FRONTEND_URL="http://127.0.0.1:5173/"
FRONTEND_LOG="$ROOT_DIR/logs/frontend.log"
FRONTEND_PID_FILE="$ROOT_DIR/.run/frontend.pid"

mkdir -p "$ROOT_DIR/.run" "$ROOT_DIR/logs"

start_backend() {
  echo "==> starting backend"
  "$BACKEND_CTL" start
  for i in $(seq 1 30); do
    if curl -sS -m 2 "$BACKEND_HEALTH_URL" >/dev/null 2>&1; then
      echo "==> backend healthy"
      return 0
    fi
    sleep 1
  done
  echo "backend health check failed: $BACKEND_HEALTH_URL"
  exit 1
}

start_frontend() {
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "frontend already running: $pid"
      return 0
    fi
  fi

  echo "==> starting frontend"
  (cd "$FRONTEND_DIR" && nohup npm run dev -- --host 127.0.0.1 --port 5173 > "$FRONTEND_LOG" 2>&1 & echo $! > "$FRONTEND_PID_FILE")
  for i in $(seq 1 30); do
    if curl -sS -m 2 "$FRONTEND_URL" >/dev/null 2>&1; then
      echo "==> frontend healthy"
      return 0
    fi
    sleep 1
  done
  echo "frontend health check failed: $FRONTEND_URL"
  exit 1
}

start_backend
start_frontend

echo "\nAll services are up:"
echo "- backend : http://127.0.0.1:8000/"
echo "- frontend: http://127.0.0.1:5173/"
echo "- toolbox : http://127.0.0.1:5173/mx"
