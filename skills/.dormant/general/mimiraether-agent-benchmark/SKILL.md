# MimirAether Agent Benchmark — 横向对比评测框架

## 触发条件

- 用户要求"评分"/"benchmark"/"对比 Agent"/"vs Hermes/OpenClaw"
- 定期自评（建议每 10 次会话跑一次）

## 架构

```
benchmarks/
  scorer.py              ← 外部判定器（不看Agent自述，只看文件系统/API）
  run_benchmark.sh        ← 环境准备 + 执行入口
  tasks/
    task_01_tool_orch/    ← 工具编排 (25%)
    task_02_codegen/      ← 代码生成 (20%)
    task_03_error_recovery/← 错误恢复 (20%)
    task_04_memory/       ← 记忆持久 (20%)
    task_05_planning/     ← 规划深度 (15%)
  results/                ← JSON 结果存档
  docker/                 ← 横向对比用 Docker 环境
```

## 五维评分卡

| 维度 | 权重 | 任务数 | 满分 |
|------|------|--------|------|
| 工具编排 | 25% | 7 检查点 | 25 |
| 代码生成 | 20% | 4 检查点 | 20 |
| 错误恢复 | 20% | 3 场景 | 15 |
| 记忆持久 | 20% | 5 字段 | 15 |
| 规划深度 | 15% | 4 阶段 | 20 |

## 公正性机制

1. **外部判定器**: 所有评分由 `scorer.py` → `tasks/*/score.py` 判定，检查文件系统/git/进程结果
2. **相同环境**: Docker 标准化
3. **相同 Prompt**: 每个 Agent 收到完全相同的 prompt.md
4. **多次取均值**: 每任务 ≥3 次
5. **结构化证据**: 每个得分点有 `evidence` 字段

## 使用方式

```bash
# 1. 准备环境
bash benchmarks/run_benchmark.sh <agent_name>

# 2. 把每个 tasks/*/prompt.md 发送给 Agent 执行

# 3. Agent 完成后评分
python3 benchmarks/scorer.py <agent_name> /tmp/benchmark-sandbox
```

## 横向对比

对比对象: OpenSpace Hermes（同源）/ OpenHands（开源）/ Cline（编码助手）

Docker 环境: `benchmarks/docker/Dockerfile` — 标准化 Ubuntu 24.04 + Python 3 + pytest + git

## MimirAether 基线

**98.7/100** (2026-05-14)
- 工具编排 100% | 代码生成 100% | 记忆持久 100% | 规划深度 100%
- 错误恢复 93.3%（只读文件处理可优化）

## 注意事项

- Task 4 跨会话记忆需要 Agent 有持久化能力，对比 Agent 可能无法完成
- 错误恢复 task 的 `broken.json` 需要 Agent 能检测 JSON 语法错误
- 所有 score.py 都是 Python 3，不依赖特定 Agent API
