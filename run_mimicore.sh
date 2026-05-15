#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="${MIMIR_REPO_ROOT:-}"
if [[ -z "$REPO_ROOT" ]]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")"
fi
cd "$REPO_ROOT"
python3 cli.py -q "调用Mimicore的produce_capsule工具，提炼关于'任务分工：织界者指挥官、MimirAether执行者、Mimicore提炼者'的知识胶囊" 2>&1
