#!/bin/bash
# MimirAether Gateway Watchdog
# 每分钟检查健康状态，挂了自动拉起

HEALTH_URL="http://127.0.0.1:18999/health"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="${MIMIR_REPO_ROOT:-}"
if [[ -z "$REPO_ROOT" ]]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")"
fi
MIMIR_DATA="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
LOG_DIR="$MIMIR_DATA/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/watchdog.log"

check_and_restart() {
    # 健康检查
    if curl -sS --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
        return 0
    fi

    # Gateway挂了 - 先清理僵尸进程
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Gateway down, restarting..." >> "$LOG_FILE"

    # 杀僵尸
    ps aux | grep "gateway[/]run.py" | awk '{print $2}' | xargs -r kill -9 2>/dev/null
    sleep 2

    # 清缓存重启（仅仓库树）
    find "$REPO_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$REPO_ROOT" -name "*.pyc" -delete 2>/dev/null || true

    (cd "$REPO_ROOT" && python3 cli.py gateway start) >> "$LOG_FILE" 2>&1

    # 等5秒验证
    sleep 5
    if curl -sS --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart OK" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart FAILED" >> "$LOG_FILE"
    fi
}

check_and_restart
