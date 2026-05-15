#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="${MIMIR_REPO_ROOT:-}"
if [[ -z "$REPO_ROOT" ]]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")"
fi
cd "$REPO_ROOT"
python3 cli.py -q "分析MimirAether当前代码状态，识别一个可以改进的地方（如代码重复、注释缺失、错误处理不足），完成一个小迭代改进并git commit" --max-iterations 10 2>&1
