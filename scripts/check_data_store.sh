#!/usr/bin/env bash
# ── 数据与存储健康检查（D 模块） ──
# 用法: ./scripts/check_data_store.sh
set -euo pipefail

MIMIR_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
OK=0
WARN=0
FAIL=0

log_ok()    { echo "  ✅ $1"; OK=$((OK+1)); }
log_warn()  { echo "  ⚠️  $1"; WARN=$((WARN+1)); }
log_fail()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

# ── D1: persistent.json 完整性 ──
PERSISTENT="$MIMIR_HOME/data/persistent.json"
if [ -f "$PERSISTENT" ]; then
    if python3 -c "import json; json.load(open('$PERSISTENT')); print('ok')" 2>/dev/null | grep -q ok; then
        P_SIZE=$(stat -c%s "$PERSISTENT" 2>/dev/null || stat -f%z "$PERSISTENT" 2>/dev/null)
        log_ok "persistent.json 可解析 ($(echo "scale=1; $P_SIZE/1024" | bc 2>/dev/null || echo '?') KB)"
    else
        log_fail "persistent.json 损坏，无法解析"
    fi
else
    log_fail "persistent.json 不存在"
fi

# ── D2: 日志大小 ──
LOG_DIR="$MIMIR_HOME/logs"
if [ -d "$LOG_DIR" ]; then
    LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
    LOG_SIZE_NUM=$(du -s "$LOG_DIR" 2>/dev/null | cut -f1)
    if [ "${LOG_SIZE_NUM:-0}" -gt 51200 ]; then  # > 50MB
        log_warn "日志目录 $LOG_SIZE (> 50MB，建议轮转)"
    else
        log_ok "日志目录 $LOG_SIZE (正常)"
    fi
else
    log_warn "日志目录不存在"
fi

# ── D3: 胶囊数 ──
CAPSULE_DIR="$MIMIR_HOME/memory/capsules"
if [ -d "$CAPSULE_DIR" ]; then
    CAP_COUNT=$(ls "$CAPSULE_DIR" 2>/dev/null | wc -l)
    if [ "$CAP_COUNT" -gt 0 ]; then
        log_ok "胶囊数: $CAP_COUNT"
    else
        log_warn "胶囊目录为空"
    fi
else
    log_warn "胶囊目录不存在"
fi

# ── D4: memory/index.html ──
MEM_INDEX="$MIMIR_HOME/memory/index.html"
if [ -f "$MEM_INDEX" ]; then
    MEM_SIZE=$(stat -c%s "$MEM_INDEX" 2>/dev/null || stat -f%z "$MEM_INDEX" 2>/dev/null)
    log_ok "memory/index.html 存在 ($(echo "scale=1; $MEM_SIZE/1024" | bc 2>/dev/null || echo '?') KB)"
else
    log_warn "memory/index.html 缺失"
fi

# ── D5: 磁盘空间 ──
DISK_USE=$(df -h "$MIMIR_HOME" 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
if [ "${DISK_USE:-100}" -gt 90 ]; then
    log_fail "磁盘使用率 ${DISK_USE}% (> 90%)"
elif [ "${DISK_USE:-100}" -gt 75 ]; then
    log_warn "磁盘使用率 ${DISK_USE}% (> 75%)"
else
    log_ok "磁盘使用率 ${DISK_USE}% (正常)"
fi

# ── D6: ground_truth.json ──
GT="$MIMIR_HOME/data/ground_truth.json"
if [ -f "$GT" ]; then
    GT_SIZE=$(stat -c%s "$GT" 2>/dev/null || stat -f%z "$GT" 2>/dev/null)
    log_ok "ground_truth.json 存在 ($(echo "scale=1; $GT_SIZE/1024" | bc 2>/dev/null || echo '?') KB)"
else
    log_warn "ground_truth.json 缺失"
fi

# ── 汇总 ──
echo ""
if [ "$FAIL" -gt 0 ]; then
    echo "D 数据存储: ❌ FAIL ($FAIL 项失败 / $OK 项通过 / $WARN 项警告)"
elif [ "$WARN" -gt 0 ]; then
    echo "D 数据存储: ⚠️  WARN ($WARN 项警告 / $OK 项通过)"
else
    echo "D 数据存储: ✅ PASS ($OK 项全部通过)"
fi
