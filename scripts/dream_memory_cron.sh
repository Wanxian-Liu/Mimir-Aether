#!/usr/bin/env bash
# 梦境记忆蒸馏 — 每日 cron 入口
# 注意：不 source .env（该文件中的 DEEPSEEK_API_KEY 常为 *** 占位符）。
#      真实 key 通过 provider_registry.credential_pool 解析，与 Gateway 同源。
set -euo pipefail

# 尝试从 symlink 解析真源路径，找不到则硬编码回退
if [ -L "$0" ]; then
    REAL_PATH="$(readlink -f "$0")"
else
    REAL_PATH="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "$REAL_PATH")" && pwd)"

# MimirAether 源码根目录
if [ -d "$SCRIPT_DIR/../agent" ] && [ -d "$SCRIPT_DIR/../.venv" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    # 回退：cron 执行时 $0 可能是 ~/.mimiraether/scripts/ 下的副本
    # 尝试从已知路径解析
    for CANDIDATE in \
        "/home/rayliu/src/MimirAether" \
        "$HOME/src/MimirAether" \
        "$(dirname "$SCRIPT_DIR")/.." \
    ; do
        if [ -d "$CANDIDATE/agent" ] && [ -d "$CANDIDATE/.venv" ]; then
            REPO_ROOT="$CANDIDATE"
            break
        fi
    done
fi

if [ -z "${REPO_ROOT:-}" ]; then
    echo "ERROR: Cannot find MimirAether source root (agent/ + .venv/ required)" >&2
    exit 1
fi

cd "$REPO_ROOT"

# 激活虚拟环境
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
