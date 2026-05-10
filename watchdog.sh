#!/bin/bash
# MimirAether Gateway Watchdog
# 每分钟检查健康状态，挂了自动拉起

HEALTH_URL="http://127.0.0.1:18999/health"
GATEWAY_DIR="/home/rayliu/.openclaw/projects/MimirAether"
LOG_FILE="$GATEWAY_DIR/logs/watchdog.log"

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
    
    # 清缓存重启
    find "$GATEWAY_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
    find "$GATEWAY_DIR" -name "*.pyc" -delete 2>/dev/null
    
    python3 "$GATEWAY_DIR/cli.py" gateway start >> "$LOG_FILE" 2>&1
    
    # 等5秒验证
    sleep 5
    if curl -sS --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart OK" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart FAILED" >> "$LOG_FILE"
    fi
}

check_and_restart
