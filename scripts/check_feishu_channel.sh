#!/usr/bin/env bash
# ── 飞书通道健康检查（B 模块） ──
# 用法: ./scripts/check_feishu_channel.sh [自测消息文本]
# 输出: 单行结论 + 证据，适合 cron / 手动跑
set -euo pipefail

MIMIR_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
GW_LOG="$MIMIR_HOME/logs/gateway.log"
AGENT_LOG="$MIMIR_HOME/logs/agent.log"
NOW=$(date +%s)
OK=0
WARN=0
FAIL=0

log_ok()    { echo "  ✅ $1"; OK=$((OK+1)); }
log_warn()  { echo "  ⚠️  $1"; WARN=$((WARN+1)); }
log_fail()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

# ── B1: Gateway 进程存活 ──
if pgrep -f 'gateway/run.py' > /dev/null 2>&1; then
    log_ok "Gateway 进程存活 (PID $(pgrep -f 'gateway/run.py' | head -1))"
else
    log_fail "Gateway 进程不存在"
fi

# ── B2: WebSocket 长连接 ──
if [ -f "$GW_LOG" ]; then
    LAST_START=$(grep -n 'Long connection task started' "$GW_LOG" | tail -1 | cut -d: -f1 || true)
    LAST_CLOSED=$(grep -n 'Disconnected' "$GW_LOG" | tail -1 | cut -d: -f1 || true)
    if [ -n "$LAST_START" ]; then
        if [ -z "$LAST_CLOSED" ] || [ "$LAST_START" -gt "$LAST_CLOSED" ]; then
            WS_TIME=$(sed -n "${LAST_START}p" "$GW_LOG" | head -c 19)
            log_ok "WebSocket 连接中 ($WS_TIME)"
        else
            CLOSED_TIME=$(sed -n "${LAST_CLOSED}p" "$GW_LOG" | head -c 19)
            log_fail "WebSocket 已断开 ($CLOSED_TIME)，需二次重启"
        fi
    else
        log_warn "WebSocket 无连接记录"
    fi
else
    log_warn "gateway.log 不存在"
fi

# ── B3: 最近发送成功率 (最近50条) ──
if [ -f "$GW_LOG" ]; then
    SEND_OK=$(grep -c 'send success' "$GW_LOG" 2>/dev/null || echo 0)
    SEND_FAIL=$(grep -c 'Fallback send also failed' "$GW_LOG" 2>/dev/null || echo 0)
    # 只看最近 5 分钟的
    FIVE_MIN_AGO=$(date -d '5 minutes ago' '+%Y-%m-%d %H:%M' 2>/dev/null || date -v-5M '+%Y-%m-%d %H:%M' 2>/dev/null || echo "")
    if [ -n "$FIVE_MIN_AGO" ]; then
        RECENT_OK=$(grep 'send success' "$GW_LOG" | awk -v cutoff="$FIVE_MIN_AGO" '$0 >= cutoff' | wc -l)
        RECENT_FAIL=$(grep 'Fallback send also failed' "$GW_LOG" | awk -v cutoff="$FIVE_MIN_AGO" '$0 >= cutoff' | wc -l)
        if [ "$RECENT_OK" -eq 0 ] && [ "$RECENT_FAIL" -eq 0 ]; then
            log_ok "最近5分钟无消息（空闲）"
        elif [ "$RECENT_FAIL" -gt 0 ]; then
            log_fail "最近5分钟发送失败 $RECENT_FAIL 条"
        else
            log_ok "最近5分钟发送成功 $RECENT_OK 条"
        fi
    else
        log_warn "无法计算时间窗口"
    fi
else
    log_warn "gateway.log 不存在，无法检查发送率"
fi

# ── B4: 收图链路 (最近2小时) ──
if [ -f "$GW_LOG" ]; then
    LAST_IMG=$(grep 'Image downloaded:' "$GW_LOG" | tail -1 | head -c 80 || true)
    if [ -n "$LAST_IMG" ]; then
        IMG_TIME=$(echo "$LAST_IMG" | head -c 19)
        log_ok "收图正常 ($IMG_TIME)"
    else
        log_ok "近期无图片消息（非异常）"
    fi
else
    log_warn "gateway.log 不存在，无法检查收图"
fi

# ── B5: Token 错误 (最近1小时) ──
if [ -f "$GW_LOG" ]; then
    TOKEN_ERR=$(grep '99991663' "$GW_LOG" | tail -1 | head -c 80 || true)
    if [ -n "$TOKEN_ERR" ]; then
        T_ERR_TIME=$(echo "$TOKEN_ERR" | head -c 19)
        # 检查是否在最近1小时内
        ONE_HOUR_AGO=$(date -d '1 hour ago' '+%Y-%m-%d %H:%M' 2>/dev/null || date -v-1H '+%Y-%m-%d %H:%M' 2>/dev/null || echo "")
        if [ -n "$ONE_HOUR_AGO" ] && [[ "$T_ERR_TIME" > "$ONE_HOUR_AGO" ]]; then
            log_fail "最近1小时有 token 过期错误 ($T_ERR_TIME)"
        else
            log_ok "无近期 token 错误（最后一次: $T_ERR_TIME）"
        fi
    else
        log_ok "零 token 错误"
    fi
fi

# ── B6: Agent 崩溃 ──
if [ -f "$AGENT_LOG" ]; then
    AGENT_RECENT_ERR=$(grep -c 'ERROR\|CRITICAL\|Traceback' "$AGENT_LOG" 2>/dev/null || echo 0)
    if [ "$AGENT_RECENT_ERR" -eq 0 ]; then
        log_ok "Agent 零错误"
    else
        log_warn "Agent 有 $AGENT_RECENT_ERR 条历史错误（最近: $(grep 'ERROR\|CRITICAL' "$AGENT_LOG" | tail -1 | head -c 80)）"
    fi
fi

# ── 汇总 ──
echo ""
if [ "$FAIL" -gt 0 ]; then
    echo "B 飞书通道: ❌ FAIL ($FAIL 项失败 / $OK 项通过 / $WARN 项警告)"
elif [ "$WARN" -gt 0 ]; then
    echo "B 飞书通道: ⚠️  WARN ($WARN 项警告 / $OK 项通过)"
else
    echo "B 飞书通道: ✅ PASS ($OK 项全部通过)"
fi
