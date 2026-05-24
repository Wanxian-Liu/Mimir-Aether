#!/usr/bin/env bash
# Hard-restart Mimir gateway: kill all gateway/run.py, clear stale PID file, start in background.
# Use when `cli.py gateway restart` leaves an old process (e.g. PID file out of sync).
#
# Usage (from anywhere):
#   MIMIR_REPO_ROOT=~/src/MimirAether MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh
#
# Logs: agent traffic → $MIMIR_AETHER_HOME/logs/agent.log (not stdout).
# This script discards gateway/run.py stdout/stderr unless LOG_TO is set.

set -euo pipefail

MIMIR_REPO_ROOT="${MIMIR_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-${HERMES_HOME:-$HOME/.mimiraether}}"

cd "$MIMIR_REPO_ROOT"

if [[ -f "$MIMIR_AETHER_HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$MIMIR_AETHER_HOME/.env"
  set +a
fi

export MIMIR_AETHER_HOME
export HERMES_HOME="${HERMES_HOME:-$MIMIR_AETHER_HOME}"

pids=$(pgrep -f 'gateway/run\.py' || true)
if [[ -n "${pids}" ]]; then
  echo "Stopping gateway PIDs: ${pids}"
  kill -TERM ${pids} 2>/dev/null || true
  sleep 2
  pids=$(pgrep -f 'gateway/run\.py' || true)
  if [[ -n "${pids}" ]]; then
    echo "Force kill: ${pids}"
    kill -9 ${pids} 2>/dev/null || true
    sleep 1
  fi
fi

rm -f "$MIMIR_AETHER_HOME/data/gateway.pid" \
      "$MIMIR_AETHER_HOME/gateway.pid" 2>/dev/null || true

mkdir -p "$MIMIR_AETHER_HOME/logs"

LOG_TO="${LOG_TO:-/dev/null}"
echo "Starting gateway (repo=$MIMIR_REPO_ROOT home=$MIMIR_AETHER_HOME log=$LOG_TO)"
nohup python3 "$MIMIR_REPO_ROOT/gateway/run.py" >>"$LOG_TO" 2>&1 &
new_pid=$!
sleep 2

if kill -0 "$new_pid" 2>/dev/null; then
  echo "Gateway started PID=$new_pid"
  health_port="${MIMIR_PORT:-18999}"
  ready=0
  for _ in $(seq 1 15); do
    if curl -sf --max-time 2 "http://127.0.0.1:${health_port}/health" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" -eq 1 ]]; then
    echo "Health: ok (http://127.0.0.1:${health_port}/health)"
  else
    echo "WARN: /health not ready after 15s — gateway process alive; retry: curl http://127.0.0.1:${health_port}/health"
  fi
  echo "Check: tail -5 \"$MIMIR_AETHER_HOME/logs/agent.log\""
  echo "       pgrep -af 'gateway/run.py'"
else
  echo "Gateway may have exited; check LOG_TO or run in foreground:"
  echo "  cd \"$MIMIR_REPO_ROOT\" && python3 gateway/run.py"
  exit 1
fi
