#!/usr/bin/env bash
# run_evolution.sh — SelfEvolutionEngine 生产接线入口
# 用法: bash scripts/run_evolution.sh [--dry-run|--report]
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PWD}/.venv/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

MODE="${1:---run}"

echo "========================================"
echo " SelfEvolutionEngine — 生产接线"
echo "========================================"

if [ "$MODE" = "--dry-run" ]; then
    echo " 模式: 分析（不写文件）"
    "${PYTHON_BIN}" scripts/run_evolution.py --dry-run
elif [ "$MODE" = "--report" ]; then
    echo " 模式: 报告（从 ledger 读取 ok%）"
    "${PYTHON_BIN}" scripts/run_evolution.py --report
else
    echo " 模式: 执行进化"
    "${PYTHON_BIN}" scripts/run_evolution.py
fi

echo "========================================"
echo " 完成"
echo "========================================"
