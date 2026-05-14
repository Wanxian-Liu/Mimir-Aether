#!/usr/bin/env bash
# =============================================================
# Agent Benchmark Runner — 横向对比评测执行脚本
# 
# 用法:
#   ./run_benchmark.sh <agent_name>
# 
# 流程:
#   1. 清理 /tmp/benchmark-sandbox
#   2. 执行所有 setup.sh 创建任务环境
#   3. 给 Agent 发送任务 prompt
#   4. 执行 scorer.py 对所有任务评分
# =============================================================
set -e

AGENT_NAME="${1:-mimir-aether}"
BENCHMARK_ROOT="$(cd "$(dirname "$0")" && pwd)"
SANDBOX="/tmp/benchmark-sandbox"

echo "🏟️  Agent Benchmark: $AGENT_NAME"
echo "================================================"

# 1. 清理
echo "🧹 清理沙盒..."
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX"

# 2. 执行各任务 setup
for task_dir in "$BENCHMARK_ROOT"/tasks/task_*; do
    task_name=$(basename "$task_dir")
    setup_script="$task_dir/setup.sh"
    if [ -x "$setup_script" ] || [ -f "$setup_script" ]; then
        echo "🔧 环境准备: $task_name"
        bash "$setup_script" "$SANDBOX"
    fi
done

echo ""
echo "📋 所有任务环境就绪。"
echo ""
echo "下一步: 将每个任务的 prompt.md 发送给 Agent，"
echo "Agent 完成后运行:"
echo "  python3 $BENCHMARK_ROOT/scorer.py $AGENT_NAME $SANDBOX"
echo ""
echo "或直接评分（如果 Agent 已经执行完毕）:"
python3 "$BENCHMARK_ROOT/scorer.py" "$AGENT_NAME" "$SANDBOX" 2>/dev/null || echo "(需要 Agent 先执行任务)"
