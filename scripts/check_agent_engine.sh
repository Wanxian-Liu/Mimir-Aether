#!/usr/bin/env bash
# ── Agent 引擎健康检查（C 模块） ──
# 用法: ./scripts/check_agent_engine.sh
set -euo pipefail

MIMIR_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
AGENT_LOG="$MIMIR_HOME/logs/agent.log"
GW_LOG="$MIMIR_HOME/logs/gateway.log"
OK=0
WARN=0
FAIL=0

log_ok()    { echo "  ✅ $1"; OK=$((OK+1)); }
log_warn()  { echo "  ⚠️  $1"; WARN=$((WARN+1)); }
log_fail()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

ONE_HOUR_AGO=$(date -d '1 hour ago' '+%Y-%m-%d %H:%M' 2>/dev/null || date -v-1H '+%Y-%m-%d %H:%M' 2>/dev/null || echo "")
FIVE_MIN_AGO=$(date -d '5 minutes ago' '+%Y-%m-%d %H:%M' 2>/dev/null || date -v-5M '+%Y-%m-%d %H:%M' 2>/dev/null || echo "")

# ── C1: Agent 进程 ──
AGENT_PID=$(pgrep -f 'agent/.*\.py' 2>/dev/null | head -1 || true)
if [ -n "$AGENT_PID" ]; then
    log_ok "Agent 进程存活 (PID $AGENT_PID)"
else
    log_ok "Agent 内嵌在 Gateway 中（无独立进程）"
fi

# ── C2: 近期崩溃 (最近1小时的 ERROR 行数) ──
if [ -f "$AGENT_LOG" ] && [ -n "$ONE_HOUR_AGO" ]; then
    # 统计最近1小时内 agent.log 的 ERROR 行（排除无害的 vision fallback）
    RECENT_ERR=$(awk -v cutoff="$ONE_HOUR_AGO" '
        $0 >= cutoff && /ERROR/ && !/Vision auto-detect/ {n++}
        END {print n+0}
    ' "$AGENT_LOG")
    if [ "$RECENT_ERR" -gt 2 ]; then
        log_fail "最近1小时有 $RECENT_ERR 条新错误"
    else
        log_ok "最近1小时错误数: $RECENT_ERR (正常)"
    fi
fi

# ── C3: Tool 孤儿 (tool must be a response) ──
ORPHAN=0
if [ -f "$AGENT_LOG" ]; then
    c=$(grep -c 'tool must be a response' "$AGENT_LOG" 2>/dev/null) || c=0
    ORPHAN=$((ORPHAN + c))
fi
if [ -f "$GW_LOG" ]; then
    c=$(grep -c 'tool must be a response' "$GW_LOG" 2>/dev/null) || c=0
    ORPHAN=$((ORPHAN + c))
fi
if [ "$ORPHAN" -eq 0 ]; then
    log_ok "零 tool 孤儿"
else
    log_fail "检测到 $ORPHAN 条 tool 孤儿"
fi

# ── C4: 最近推理耗时 ──
if [ -f "$AGENT_LOG" ]; then
    LAST_TURN=$(grep -P 'turn.*total=' "$AGENT_LOG" 2>/dev/null | tail -1 || true)
    if [ -n "$LAST_TURN" ]; then
        TOTAL_TIME=$(echo "$LAST_TURN" | grep -oP 'total=\K[0-9.]+' 2>/dev/null || echo "?")
        TURN_TIME=$(echo "$LAST_TURN" | head -c 19)
        log_ok "最近推理 ${TOTAL_TIME}s ($TURN_TIME)"
    else
        log_ok "空闲（无推理记录）"
    fi
fi

# ── C5: 近期错误趋势 ──
if [ -f "$AGENT_LOG" ] && [ -n "$FIVE_MIN_AGO" ]; then
    RECENT_5=$(awk -v cutoff="$FIVE_MIN_AGO" '
        $0 >= cutoff && /ERROR/ && !/Vision auto-detect/ {n++}
        END {print n+0}
    ' "$AGENT_LOG")
    if [ "$RECENT_5" -gt 2 ]; then
        log_fail "最近5分钟有 $RECENT_5 条错误"
    else
        log_ok "最近5分钟错误: $RECENT_5 条 (正常)"
    fi
fi

# ── C6: 上下文压缩 ──
if [ -f "$AGENT_LOG" ]; then
    LAST_COMPRESS=$(grep -E 'compress|truncat|budget' "$AGENT_LOG" 2>/dev/null | tail -1 | head -c 100 || true)
    if [ -n "$LAST_COMPRESS" ]; then
        log_ok "上下文管理活跃"
    else
        log_ok "无上下文压缩记录"
    fi
fi

# ── 汇总 ──
echo ""
if [ "$FAIL" -gt 0 ]; then
    echo "C Agent引擎: ❌ FAIL ($FAIL 项失败 / $OK 项通过 / $WARN 项警告)"
elif [ "$WARN" -gt 0 ]; then
    echo "C Agent引擎: ⚠️  WARN ($WARN 项警告 / $OK 项通过)"
else
    echo "C Agent引擎: ✅ PASS ($OK 项全部通过)"
fi
