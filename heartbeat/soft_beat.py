#!/usr/bin/env python3
"""
软心跳 — 在每次工具调用后追加记录。

用法（从 agent 调用）：
    python3 heartbeat/soft_beat.py <tool_name> <duration_ms> <status>

写入：heartbeat/logs/soft_beat.log
"""
import sys
import os
from datetime import datetime, timezone

HEARTBEAT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(HEARTBEAT_DIR, "logs", "soft_beat.log")


def record(tool_name: str, duration_ms: float, status: str, detail: str = ""):
    """记录一次工具调用"""
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    line = f"{ts} | {tool_name} | {duration_ms:.0f}ms | {status}"
    if detail:
        line += f" | {detail}"

    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

    # 保持日志可管理
    _trim(2000)


def _trim(max_lines: int = 2000):
    """只保留最新的 N 条记录"""
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(LOG_FILE, "w") as f:
                f.writelines(lines[-max_lines:])
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: soft_beat.py <tool_name> <duration_ms> <status> [detail]")
        sys.exit(1)

    tool_name = sys.argv[1]
    duration_ms = float(sys.argv[2])
    status = sys.argv[3]
    detail = sys.argv[4] if len(sys.argv) > 4 else ""
    record(tool_name, duration_ms, status, detail)
    print(f"[OK] Soft beat: {tool_name} | {duration_ms:.0f}ms | {status}")
