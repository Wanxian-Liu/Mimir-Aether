#!/usr/bin/env bash
# Basic smoke checks for local development.
#
# IMPORTANT: `cli.py gateway health` expects HTTP /health on 127.0.0.1:18999 (or
# MIMIR_PORT). That endpoint exists only when `platforms.api_server` is enabled
# in ~/.openclaw/config.yaml. Without it, this script may report failure even if
# the gateway is running other platforms. See docs/gateway-cli-health.md.
#
# Cron: scheduled jobs run inside the gateway process, not from `cli.py cron run` alone.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${MIMIR_PORT:-18999}"
URL="http://127.0.0.1:${PORT}/health"

echo "== Smoke: gateway HTTP health (${URL}) =="
if command -v curl >/dev/null 2>&1; then
  curl -sS -f "$URL" | head -c 400 || {
    echo "FAIL: no /health (enable platforms.api_server in ~/.openclaw/config.yaml)" >&2
    exit 1
  }
  echo
else
  echo "SKIP: curl not installed"
fi

echo "== Smoke: cli gateway health =="
python3 cli.py gateway health

echo "OK"
