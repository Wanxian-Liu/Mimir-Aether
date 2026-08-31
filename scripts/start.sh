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
# Optional hint for tooling; gateway reads bind/port from config / platform env, not CLI.
export GATEWAY_PORT="${GATEWAY_PORT:-${PORT:-18789}}"
# 统一用项目 venv（系统 python3 无 torch/ST -> chroma 维度不匹配假数据）
PYTHON_BIN="${ROOT}/.venv/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi
exec "${PYTHON_BIN}" "$MIMIR_AETHER_HOME/gateway/run.py" "$@"
