#!/usr/bin/env bash
# Standalone gateway entry: set project home and align HERMES_HOME for vendored hermes_cli.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$ROOT}"
export HERMES_HOME="${HERMES_HOME:-$MIMIR_AETHER_HOME}"
cd "$MIMIR_AETHER_HOME"
if [[ -f "$MIMIR_AETHER_HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$MIMIR_AETHER_HOME/.env"
  set +a
fi
PORT="${GATEWAY_PORT:-${PORT:-18789}}"
exec python3 "$MIMIR_AETHER_HOME/gateway/run.py" --port "$PORT" "$@"
