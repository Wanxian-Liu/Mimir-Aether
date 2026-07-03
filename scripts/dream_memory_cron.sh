#!/usr/bin/env bash
# 梦境记忆蒸馏 — 每日 cron 入口
# 依赖: DEEPSEEK_API_KEY（从 ~/.mimiraether/.env 加载）
set -euo pipefail

MIMIR_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
if [ -f "$MIMIR_HOME/.env" ]; then
    set -a
    source "$MIMIR_HOME/.env"
    set +a
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# 确保在正确的虚拟环境下运行
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 -c "
import sys
sys.path.insert(0, '.')
from agent.dream_memory import sync_run_dream_cycle
result = sync_run_dream_cycle(dry_run=False)
print(result)
"
