# IQ55-11a: 进化管道 `outcome=planned` 机制文档

## 问题

`evolution_ledger.json` 有 4 条记录，全部 `reason: "outcome=planned"`。
没有任何一条记录是 `outcome=applied`。

## 根因

`SelfEvolutionEngine`（`agent/self_evolution/engine.py`）：

1. **`run_cycle()` 定义自 2026-06-01**，但代码库里**零导入、零实例化**（grep 全库无 `from.*self_evolution.*import`）
2. 引擎默认 `outcome="planned"`（engine.py:227）— 因为设计是「先规划，再应用」，但**应用回调（execute_callback）从未传入**
3. 现有的 4 条账目是通过**另一套进化路径**写入的——非 `SelfEvolutionEngine.run_cycle`，因为该函数从未被调用

## 真实进化路径

当前存在两套独立的进化机制：

| 路径 | 代码位置 | 状态 |
|:----:|---------|:----:|
| **SelfEvolutionEngine** | `agent/self_evolution/engine.py` | 定义完整但**从未接线**——零调用、零导入 |
| **brain_metrics/evolution eval** | `scripts/brain_metrics_snapshot.py` + `mimir_ops evolution_eval` | 活跃——从 evolution log 提取行级 ok% |

## `outcome=planned` 的含义

这个词暂不代表「IC 通过但未 apply」，而是**引擎代码存在但从未真正跑过**。账目本身的源头无法追溯（可能是早期测试写入）。

## 修复方向（IQ55-11b）

要使 `outcome=applied` 出现，需要：

1. **接线**：在 agent 循环的某个入口（如 cron 或 post-task hook）实例化 `SelfEvolutionEngine`
2. **传回调**：`run_cycle(execute_callback=...)` 中传入实际写盘的函数
3. **环境门控**：`MIMIR_AUTO_EVOLVE=1` 控制启用

## 当前误区（诚实承认）

**我之前在自评中引用的 "evolution ok% = 50%" 和 "4 条 planned" 数字是准确的**（来自 ledger + brain_metrics），但我错误地把它们解释为「IC 通过但未 apply」。实际上这个引擎根本就没在生产环境运行过。这 4 条账目可能是早期测试写入的无源数据。
