#!/usr/bin/env bash
# Stop all gateway/run.py, then start exactly one (uses repo .venv if present).
set -euo pipefail

MIMIR_REPO_ROOT="${MIMIR_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-${HERMES_HOME:-$HOME/.mimiraether}}"
PYTHON="${MIMIR_PYTHON:-$MIMIR_REPO_ROOT/.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON="python3"

cd "$MIMIR_REPO_ROOT"
if [[ -f "$MIMIR_AETHER_HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$MIMIR_AETHER_HOME/.env"
  set +a
fi
export MIMIR_AETHER_HOME
export HERMES_HOME="${HERMES_HOME:-$MIMIR_AETHER_HOME}"

_gateway_pids() {
  # Match only real python gateway processes (not bash wrappers that embed the path).
  local pid comm
  while read -r pid comm; do
    [[ "$comm" == python || "$comm" == python3 ]] || continue
    echo "$pid"
  done < <(pgrep -f 'gateway/run\.py' -l 2>/dev/null || true)
}

echo "Stopping gateway (python only) ..."
# Do not pkill bare 'gateway/run.py' — matches Cursor/bash wrapper lines.
while read -r pid; do
  [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null || true
done < <(_gateway_pids)
sleep 2
while read -r pid; do
  [[ -n "$pid" ]] && kill -9 "$pid" 2>/dev/null || true
done < <(_gateway_pids)
sleep 1

rm -f "$MIMIR_AETHER_HOME/data/gateway.pid" "$MIMIR_AETHER_HOME/gateway.pid" 2>/dev/null || true
mkdir -p "$MIMIR_AETHER_HOME/logs"

mapfile -t _left < <(_gateway_pids)
if [[ "${#_left[@]}" -gt 0 ]]; then
  echo "ERROR: still ${#_left[@]} gateway process(es) after pkill" >&2
  ps -p "${_left[*]}" -o pid,cmd 2>/dev/null || true
  exit 1
fi

echo "Starting gateway: $PYTHON"
nohup "$PYTHON" "$MIMIR_REPO_ROOT/gateway/run.py" >>"$MIMIR_AETHER_HOME/logs/gateway-stdout.log" 2>&1 &
new_pid=$!
sleep 5

if ! kill -0 "$new_pid" 2>/dev/null; then
  echo "ERROR: gateway exited; tail log:" >&2
  tail -15 "$MIMIR_AETHER_HOME/logs/gateway-stdout.log" >&2 || true
  exit 1
fi

mapfile -t _running < <(_gateway_pids)
count="${#_running[@]}"
port="${MIMIR_PORT:-18999}"
health=$(curl -sf --max-time 5 "http://127.0.0.1:${port}/health" 2>/dev/null || true)

echo "pid=$new_pid process_count=$count"
if echo "$health" | grep -q '"status"'; then
  echo "health=ok http://127.0.0.1:${port}/health"
else
  echo "WARN: /health not ready yet (process alive)"
fi

if [[ "$count" -gt 1 ]]; then
  echo "ERROR: multiple gateway processes" >&2
  ps -p "${_running[*]}" -o pid,cmd 2>/dev/null || true
  exit 1
fi
