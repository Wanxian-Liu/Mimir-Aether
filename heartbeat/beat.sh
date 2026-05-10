#!/usr/bin/env bash
# ============================================================
# 心跳入口 — 一键触发所有心跳组件
# 用法: ./heartbeat/beat.sh [--snapshot]
#   --snapshot  同时运行能力快照（较慢，按需使用）
# ============================================================
set -euo pipefail

HEARTBEAT_DIR="$(cd "$(dirname "$0")" && pwd)"
HARD_BEAT="${HEARTBEAT_DIR}/hard_beat.sh"
SOFT_BEAT="${HEARTBEAT_DIR}/soft_beat.py"
SNAPSHOT="${HEARTBEAT_DIR}/capability_snapshot.py"

echo "=== MimirAether Heartbeat ==="

# 1. 硬心跳
echo "[1/2] Hard beat..."
bash "${HARD_BEAT}"

# 2. 能力快照（可选）
if [[ "${1:-}" == "--snapshot" ]]; then
    echo "[2/2] Capability snapshot..."
    python3 "${SNAPSHOT}"
else
    echo "[2/2] Skipped (add --snapshot for capability check)"
fi

echo "=== Heartbeat complete ==="
