#!/usr/bin/env bash
# 梦境记忆蒸馏 — 每日 cron 入口
# 注意：不 source .env（该文件中的 DEEPSEEK_API_KEY 常为 *** 占位符）。
#      真实 key 通过 provider_registry.credential_pool 解析，与 Gateway 同源。
set -euo pipefail

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
