#!/usr/bin/env bash
# run_evolution.sh — SelfEvolutionEngine 生产接线入口
# 用法: bash scripts/run_evolution.sh [--dry-run]
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:---run}"

echo "========================================"
echo " SelfEvolutionEngine — 生产接线"
echo "========================================"

if [ "$MODE" = "--dry-run" ]; then
    echo " 模式: 分析（不写文件）"
    python3 scripts/run_evolution.py --dry-run
else
    echo " 模式: 执行进化"
    python3 scripts/run_evolution.py
fi

echo "========================================"
echo " 完成"
echo "========================================"
