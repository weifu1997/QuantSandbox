#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.run/backend.pid"
LOG_FILE="$ROOT_DIR/logs/backend.log"
HOST="127.0.0.1"
PORT="8000"
READY_URL="http://$HOST:$PORT/openapi.json"
READY_TIMEOUT_SECONDS="10"
READY_INTERVAL_SECONDS="0.2"

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

find_port_pids() {
  python3 - "$PORT" <<'PY'
import re
import subprocess
import sys
port = sys.argv[1]
try:
    out = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL)
except Exception:
    sys.exit(0)
pattern = re.compile(rf":{re.escape(port)}\s+.*pid=(\d+)")
seen = []
for line in out.splitlines():
    if f":{port}" not in line:
        continue
    match = pattern.search(line)
    if match:
        pid = match.group(1)
        if pid not in seen:
            seen.append(pid)
for pid in seen:
    print(pid)
PY
}

cmdline_for_pid() {
  local pid="$1"
  if [[ -r "/proc/$pid/cmdline" ]]; then
    tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
  fi
}

show_port_owners() {
  local pids
  pids="$(find_port_pids || true)"
  if [[ -z "${pids:-}" ]]; then
    echo "port $PORT owner: unknown"
    return 0
  fi
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    local cmd=""
    cmd="$(cmdline_for_pid "$pid")"
    echo "port $PORT occupied by pid=$pid cmd=${cmd:-unknown}"
  done <<< "$pids"
}

stop_port_owners() {
  local pids
  pids="$(find_port_pids || true)"
  [[ -z "${pids:-}" ]] && return 0
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done <<< "$pids"
  sleep 1
  pids="$(find_port_pids || true)"
  [[ -z "${pids:-}" ]] && return 0
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done <<< "$pids"
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

wait_for_backend_ready() {
  python3 - "$READY_URL" "$READY_TIMEOUT_SECONDS" "$READY_INTERVAL_SECONDS" "$PID_FILE" <<'PY'
import json
import sys
import time
import urllib.request
from pathlib import Path

ready_url = sys.argv[1]
timeout = float(sys.argv[2])
interval = float(sys.argv[3])
pid_file = Path(sys.argv[4])
deadline = time.time() + timeout
last_error = "unknown"

while time.time() < deadline:
    pid = pid_file.read_text().strip() if pid_file.exists() else ""
    if not pid:
        print("backend readiness failed: pid file missing", file=sys.stderr)
        sys.exit(1)
    proc_path = Path(f"/proc/{pid}")
    if not proc_path.exists():
        print(f"backend readiness failed: pid {pid} exited before ready", file=sys.stderr)
        sys.exit(1)
    try:
        with urllib.request.urlopen(ready_url, timeout=2) as r:
            if r.status == 200:
                try:
                    json.load(r)
                except Exception:
                    pass
                print("ready")
                sys.exit(0)
            last_error = f"HTTP {r.status}"
    except Exception as e:
        last_error = repr(e)
    time.sleep(interval)

print(f"backend readiness timeout after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

start() {
  if is_running >/dev/null 2>&1; then
    echo "backend already running: $(cat "$PID_FILE")"
    show_port_owners
    exit 0
  fi

  local foreign_pids
  foreign_pids="$(find_port_pids || true)"
  if [[ -n "${foreign_pids:-}" ]]; then
    echo "backend cannot start: port $PORT is already in use"
    show_port_owners
    echo "hint: run '$0 stop' to reclaim the port or stop the foreign process manually"
    exit 1
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

  if wait_for_backend_ready >/dev/null; then
    echo "backend started: $(cat "$PID_FILE")"
    echo "ready_url: $READY_URL"
    echo "log: $LOG_FILE"
  else
    echo "backend failed to become ready"
    show_port_owners
    echo "recent log tail:"
    tail -n 20 "$LOG_FILE" || true
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
    echo "backend not running (pid file missing or stale)"
  fi

  local lingering
  lingering="$(find_port_pids || true)"
  if [[ -n "${lingering:-}" ]]; then
    echo "port $PORT still occupied after normal stop; terminating lingering owner(s)"
    show_port_owners
    stop_port_owners
    lingering="$(find_port_pids || true)"
    if [[ -n "${lingering:-}" ]]; then
      echo "warning: port $PORT is still occupied"
      show_port_owners
      exit 1
    fi
    echo "lingering port owner(s) stopped"
  fi
  rm -f "$PID_FILE"
}

status() {
  local pid_status="stopped"
  if is_running >/dev/null 2>&1; then
    pid_status="running: $(cat "$PID_FILE")"
  elif [[ -f "$PID_FILE" ]]; then
    pid_status="stale pid file: $(cat "$PID_FILE" 2>/dev/null || echo unknown)"
  fi
  echo "$pid_status"
  echo "ready_url: $READY_URL"
  echo "log: $LOG_FILE"

  local port_pids
  port_pids="$(find_port_pids || true)"
  if [[ -n "${port_pids:-}" ]]; then
    show_port_owners
  else
    echo "port $PORT is free"
  fi
}

doctor() {
  echo "[backend doctor]"
  echo "root_dir: $ROOT_DIR"
  echo "pid_file: $PID_FILE"
  echo "log_file: $LOG_FILE"
  echo "host: $HOST"
  echo "port: $PORT"
  echo "ready_url: $READY_URL"
  echo "ready_timeout_seconds: $READY_TIMEOUT_SECONDS"
  echo "ready_interval_seconds: $READY_INTERVAL_SECONDS"
  echo

  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    echo "pid_file_state: present"
    echo "pid_file_value: ${pid:-empty}"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "pid_process_state: alive"
      echo "pid_process_cmd: $(cmdline_for_pid "$pid")"
    else
      echo "pid_process_state: stale"
    fi
  else
    echo "pid_file_state: missing"
  fi
  echo

  local port_pids
  port_pids="$(find_port_pids || true)"
  if [[ -z "${port_pids:-}" ]]; then
    echo "port_state: free"
  else
    echo "port_state: occupied"
    while IFS= read -r pid; do
      [[ -z "$pid" ]] && continue
      local cmd
      cmd="$(cmdline_for_pid "$pid")"
      echo "port_owner_pid: $pid"
      echo "port_owner_cmd: ${cmd:-unknown}"
      if [[ "$cmd" == *"python3 -m uvicorn backend.main:app"* ]]; then
        echo "port_owner_matches_backend: yes"
      else
        echo "port_owner_matches_backend: no"
      fi
      if [[ -f "$PID_FILE" ]] && [[ "$(cat "$PID_FILE" 2>/dev/null || true)" == "$pid" ]]; then
        echo "port_owner_matches_pid_file: yes"
      else
        echo "port_owner_matches_pid_file: no"
      fi
      echo
    done <<< "$port_pids"
  fi

  if [[ -f "$LOG_FILE" ]]; then
    echo "log_file_state: present"
    echo "log_tail:"
    tail -n 5 "$LOG_FILE" || true
  else
    echo "log_file_state: missing"
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
  doctor) doctor ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|doctor}"
    exit 1
    ;;
esac
