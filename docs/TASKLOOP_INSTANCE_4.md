# TaskLoop Instance: #4 TaskLoop 架构设计

## 任务参数

task: "将 docs/TASKLOOP_ARCH.md 的设计落地为可运行的 scripts/task_loop.py"
eval_cmd: "cd ~/src/MimirAether && python3 scripts/task_loop.py --dry-run --config docs/TASKLOOP_INSTANCE_4.json 2>&1 | grep -c 'OK'"
target_score: 5
max_rounds: 1
max_time: "60m"
no_go: ["不要改动 mimicore/", "不要改 memory/capsules/ 下的内容", "不要动 OpenClaw 路径"]

## 交付物清单

| # | 交付物 | 描述 |
|---|--------|------|
| D1 | `scripts/task_loop_config.py` | 数据结构: TaskLoopConfig, RoundState, StopReason |
| D2 | `scripts/task_loop.py` | 引擎主程序: while True + eval + gate + stop |
| D3 | `scripts/task_loop_test.py` | 自测: mock eval 5轮, 验证 3 条停止条件 |
| D4 | `docs/TASKLOOP_INSTANCE_4.json` | 本任务的 JSON 配置 (dry-run 用) |
| D5 | `run_ralph_tier0.sh` 通过 | 不改旧代码, tier0 绿 |

## 验收标准

1. `task_loop.py --dry-run` 跑完 5 轮 mock 循环不出错
2. 3 条停止条件各触发一次: 目标达成 / 轮次耗尽 / 连续退化
3. results.tsv 正确写入 5 行
4. run_ralph_tier0.sh 仍然全绿

## 评测定义

每轮 mock eval 返回固定序列: [0.5, 0.6, 0.7, 0.7, 0.7]
- Round 3: 目标达成 (0.7 >= target 0.7) → 触发 TARGET_REACHED
- 验证 results.tsv 有 3 行 + 停止原因为 TARGET_REACHED
