#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.run/backend.pid"
LOG_FILE="$ROOT_DIR/logs/backend.log"
HOST="127.0.0.1"
PORT="8000"

mkdir -p "$ROOT_DIR/.run" "$ROOT_DIR/logs"

is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$pid"
      return 0
    fi
  fi
  return 1
}

get_exported_value() {
  local key="$1"
  local value=""
  value="$(grep -hE "^export ${key}=" "$HOME/.profile" "$HOME/.bashrc" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

start() {
  if is_running >/dev/null 2>&1; then
    echo "backend already running: $(cat "$PID_FILE")"
    exit 0
  fi

  if [[ -z "${MX_APIKEY:-}" ]]; then
    MX_APIKEY="$(get_exported_value MX_APIKEY)"
    export MX_APIKEY
  fi
  if [[ -z "${MX_API_URL:-}" ]]; then
    MX_API_URL="$(get_exported_value MX_API_URL)"
  fi
  if [[ -z "${MX_API_URL:-}" ]]; then
    MX_API_URL="https://mkapi2.dfcfs.com/finskillshub"
  fi
  export MX_API_URL
  nohup env MX_APIKEY="${MX_APIKEY:-}" MX_API_URL="${MX_API_URL:-}" python3 -m uvicorn backend.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 1
  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "backend started: $(cat "$PID_FILE")"
    echo "log: $LOG_FILE"
  else
    echo "backend failed to start"
    exit 1
  fi
}

stop() {
  if is_running >/dev/null 2>&1; then
    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "backend stopped"
  else
    rm -f "$PID_FILE"
    echo "backend not running"
  fi
}

status() {
  if is_running >/dev/null 2>&1; then
    echo "running: $(cat "$PID_FILE")"
    echo "log: $LOG_FILE"
  else
    echo "stopped"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart)
    stop
    start
    ;;
  status) status ;;
  logs)
    tail -n 200 -f "$LOG_FILE"
    ;;
  *)
    echo "usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
