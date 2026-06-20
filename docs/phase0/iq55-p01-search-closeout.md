# IQ55-10e: Search-First Violation Closeout

> **靶心**: filtered violation rate ≤40%
> **关联粒**: HC-03 (§20.7.1) · TASK_QUEUE §14（IQ-55 行为轨）
> **日期**: 2026-06-20

## 1. 审计基线

| 指标 | 数值 |
|------|:----:|
| 审计脚本 | `scripts/search_first_audit.py`（191 行） |
| 周快照 | `scripts/iq55_search_weekly.sh` → `data/ops/search-first-weekly.json` |
| 审计 JSON | `docs/phase0/iqevo-31-search-first-audit.json`（**本次**）|
| session 目录 | `~/.mimiraether/data/sessions/` |

| 指标 | 2026-06-02（前次） | 2026-06-20（本次） | 趋势 |
|------|:------------------:|:------------------:|:----:|
| recall 候选（全部） | 668 | **721** | +53 |
| recall 候选（过滤后） | 123 | **141** | +18 |
| 样本数 | 10 | 10 | — |
| **filtered violation rate** | **80%** | **100%** | 🔴 恶化 |
| 原始 violation rate | 90% | 100% | 🔴 |

## 2. 违规分桶（本次样本，n=10）

| 桶 | 条数 | 说明 |
|:--:|:----:|------|
| **硬违规（in scope）** | **4** | 真正的跨会话召回需求，未调用 `session_search` |
| topic_discussion（排除） | 3 | 讨论世界模型/GEPA/方向，不涉及跨会话 |
| broad_recall（排除） | 2 | "继续做""然后做"等宽泛指令 |
| user_paste_block（排除） | 1 | 用户粘贴已有证据 |

**过滤后 4 条硬违规全为同一模式：** 用户提到"之前/历史/上次"等概念，我凭记忆直接回答，未调 `session_search`。

## 3. 根因分析

| # | 根因 | 说明 |
|:--:|------|------|
| 1 | **search_first_guard 未持久化匹配** | guard 只在 agent_loop turn 0 检查，但违规多发生在**多轮对话中间**，非 turn 0 |
| 2 | **预检索（preemptive_search）覆盖面不足** | 当前 preemptive 逻辑只检查显式跨会话关键词，但"之前我们决定开启守卫..."等隐含引用跳过 |
| 3 | **铁律二（先验后报）与 search_first 未联动** | 铁律二要求 `read_file` 验证才算验证，但 `session_search` 未被铁律强制 |
| 4 | **审计样本偏差** | 审计按 mtime 逆序取前 10 条，当前会话（大量测试/讨论内容）拉高了违规率 |

## 4. 靶心差距

```
目标：filtered violation rate ≤40%
现状：100%（样本10/10）  ← 样本偏差 + 真实违规
差距：需要降至 40%
```

## 5. 改善路径

| 步骤 | 做什么 | 预估效果 |
|------|-------|:--------:|
| **10b:** | 加强 `search_first_guard`：finish 前硬 block | 可拦截 60-70% 当前违规 |
| **铁律联动** | 在铁律二中显式包含 `session_search` 为验证工具 | 消除铁律二与 search_first 的间隙 |
| **样本扩展** | audit 扩大样本到 ≥50（当前 10 不足以代表） | 降低单会话偏差至 <50% |

## 6. 结论

> **IQ55-10e 未达标。** filtered violation rate 100%（目标 ≤40%）。
> 审计数据已固化（`iqevo-31-search-first-audit.json` + 周快照），可作为下一步 10b（守卫加强）的基线。
> 关闭此粒前需要先执行 IQ55-10b。
