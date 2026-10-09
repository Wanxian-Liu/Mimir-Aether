#!/bin/bash
# N13 段1 · 闭环看门狗 cron 入口（零 LLM · 每 5 分钟）
# 代码真源 = $HOME/src/MimirAether/scripts/state_watchdog.py —— 本文件只是 cron 侧薄壳
# （cron 的 script 字段只认 <MIMIR_AETHER_HOME>/scripts/ 下的相对名，故须在此放壳）。
# 零对外：deliver=local，不发消息；只在超 deadline 时落 state-alerts.jsonl。
# 路径不写死：一律由 $HOME 推（公开仓禁绝对 home 路径 · pre-commit 闸）。
set -uo pipefail
: "${HOME:?HOME must be set -- 否则会静默扫 0 张卡}"
REPO="${MIMIR_REPO_HOME:-$HOME/src/MimirAether}"
PY="$REPO/.venv/bin/python3"
W="$REPO/scripts/state_watchdog.py"
exec "$PY" "$W" "$@"
