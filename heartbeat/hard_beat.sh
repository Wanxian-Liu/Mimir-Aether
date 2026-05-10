#!/usr/bin/env bash
# ============================================================
# 硬心跳 — 每5分钟记录时间戳 + 活跃状态
# 由 cron 触发: */5 * * * * bash /path/to/hard_beat.sh
# 写入: heartbeat/logs/hard_beat.log
# ============================================================
set -euo pipefail

# 定位到项目根目录（兼容 cron 的有限 PATH）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/hard_beat.log"

# 确保日志目录存在
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date --iso-8601=seconds)

# ---- 活跃性检查 ----

# 1. 进程数
PROC_COUNT=$(ps aux --no-headers 2>/dev/null | wc -l || echo "0")

# 2. 磁盘用量
DISK_USAGE=$(df "${PROJECT_DIR}" --output=pcent 2>/dev/null | tail -1 | tr -d ' %' || echo "0")

# 3. Hermes 进程状态
HERMES_RUNNING="no"
if pgrep -f "hermes" >/dev/null 2>&1; then
    HERMES_RUNNING="yes"
fi

# 4. Agent 进程存活检查（MimirAether / Python agent 进程）
AGENT_ALIVE="no"
if pgrep -f "mimir" >/dev/null 2>&1 || pgrep -f "openclaw" >/dev/null 2>&1; then
    AGENT_ALIVE="yes"
fi

# 5. 内存使用（系统总览）
MEM_TOTAL=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo "0")
MEM_USED=$(free -m 2>/dev/null | awk '/^Mem:/{print $3}' || echo "0")

# 6. 最近一次软心跳时间 + 时间差
LAST_SOFT="never"
SOFT_GAP_SEC="N/A"
SOFT_LOG="${LOG_DIR}/soft_beat.log"
if [ -f "${SOFT_LOG}" ] && [ -s "${SOFT_LOG}" ]; then
    LAST_SOFT_LINE=$(tail -1 "${SOFT_LOG}")
    LAST_SOFT=$(echo "${LAST_SOFT_LINE}" | awk '{print $1, $2}' | tr -d '|')
    # 计算时间差（秒）
    if [ "${LAST_SOFT}" != "never" ] && command -v python3 &>/dev/null; then
        SOFT_GAP_SEC=$(python3 -c "
from datetime import datetime, timezone
try:
    now = datetime.now(timezone.utc)
    last = datetime.fromisoformat('${LAST_SOFT}')
    delta = (now - last).total_seconds()
    print(f'{delta:.0f}')
except:
    print('N/A')
")
    fi
fi

# ---- 写入日志 ----
echo "${TIMESTAMP} | alive | procs=${PROC_COUNT} | disk=${DISK_USAGE}% | mem=${MEM_USED}/${MEM_TOTAL}MB | hermes=${HERMES_RUNNING} | agent=${AGENT_ALIVE} | last_soft=${LAST_SOFT} | soft_gap=${SOFT_GAP_SEC}s" >> "${LOG_FILE}"

# 只保留最近 2000 条记录
tail -2000 "${LOG_FILE}" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "${LOG_FILE}"

# ---- 健康告警（可选） ----
if [ "${DISK_USAGE}" -gt 90 ]; then
    echo "[WARN] 磁盘使用率 ${DISK_USAGE}% 超过 90% !" >> "${LOG_FILE}"
fi

# 如果软心跳超过 30 分钟无更新，发出告警
if [ "${SOFT_GAP_SEC}" != "N/A" ] && [ "${SOFT_GAP_SEC}" -gt 1800 ] 2>/dev/null; then
    echo "[WARN] 软心跳已 ${SOFT_GAP_SEC} 秒（>30分钟）未更新，agent 可能已停止工作" >> "${LOG_FILE}"
fi
