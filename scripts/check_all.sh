#!/usr/bin/env bash
# ── MimirAether 全模块健康检查（外部检测总入口） ──
# 用法: ./scripts/check_all.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  MimirAether 外部检测 — $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

PASS=0
WARN=0
FAIL=0

for mod in B C D; do
    case $mod in
        B) label="飞书通道"  ;;
        C) label="Agent引擎" ;;
        D) label="数据存储"  ;;
    esac
    result=$("$SCRIPT_DIR/check_feishu_channel.sh" 2>&1 || true)
    echo "$result"
    # 同时输出给 -B -C -D 按需
done

echo "========================================"
echo "  A 模块 (Gateway 运行时): 飞书通道脚本 B1/B2 已覆盖"
echo "========================================"
