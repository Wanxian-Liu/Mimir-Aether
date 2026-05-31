# EV-Q04 — 智商评分 rubric（2026-05-27 复评 · IQ-EVO-46 · #6）

> 刷新自 [IQ_SCORING_RUBRIC.md](../IQ_SCORING_RUBRIC.md)；依据 Q01–Q03 phase0 真源。
> **本次复评**：Wave 7 Gate C/D 结案（analysis→evolution 时序 · staging SKILL 写入 · 1c 有界策略/压缩 · contract 1C-01～07）。

## 摘要

- **加权总分 4.9/10**（精算 **4.875→4.9**；Wave 6 **4.8**）。
- 上调：**#1 学习能力**（Gate C 路径 + 1c 代码，env 门闩）、**#10 数据闭环**（时序修复 + eval）、**#2 自适应阈值**（1c Compressor 第二档，默认关）。
- 距 5.5 目标差 **0.6** → **documented exception**（见 Wave 7 closeout）。
- **诚实声明**：4.9 = Wave 7 **工程与门禁**闭环；**不是**生产默认「每天自己变好」或 IntentPredictor 上线。

## 10 维评分

| # | 子维度 | 权 | 现评 | 目标 | 依据（2026-05-27 Wave 7 后） |
|---|--------|:--:|:--:|:--:|------|
| 1 | 学习能力 | 15% | **3.5**↑ | 7.0 | Gate C：`MIMIR_AUTO_EVOLVE=1` + 真实 SKILL 写入（§41/42）；1c policy（`MIMIR_AUTO_1C_POLICY` **默认关**）；非 Hermes 级 nudge |
| 2 | 自适应阈值 | 10% | **4.5**↑ | 7.5 | Top-3 AutoTuner + **1c** Compressor 有界旋钮（与 1b 正交） |
| 3 | 反馈收集 | 10% | 5.0 | 6.0 | FeedbackCollector + 生产 JSONL |
| 4 | 工具选择智能 | 10% | 5.5 | 8.0 | Q02 排名/降级 |
| 5 | Prompt 优化 | 10% | 5.5 | 8.0 | search-first + tool_quality + analysis artifact 只读 |
| 6 | 错误恢复 | 10% | 6.0 | 8.0 | RecoveryMixin + DecisionRing（+1c D* 可选） |
| 7 | 上下文管理 | 10% | **8.0** | 8.0 | 🟢 触顶 |
| 8 | 意图理解 | 10% | 3.5 | 7.5 | 离线 intent MVP；**无**生产 IntentPredictor |
| 9 | 模型路由 | 5% | 4.0 | 7.0 | 默认模型为主 |
| 10 | 数据闭环 | 10% | **5.5**↑ | 6.0 | IQ-EVO-40 时序；Gate C eval 3×；feedback→tune/1c/evolve 分文件 |

## 加权

`3.5×0.15 + 4.5×0.10 + 5.0×0.10 + 5.5×0.10 + 5.5×0.10 + 6.0×0.10 + 8.0×0.10 + 3.5×0.10 + 4.0×0.05 + 5.5×0.10`

= `0.525 + 0.45 + 0.50 + 0.55 + 0.55 + 0.60 + 0.80 + 0.35 + 0.20 + 0.55`

= **4.875 → 4.9/10**

## vs Wave 6（4.8）

| 变化 | Δ 加权 | 说明 |
|------|:------:|------|
| 总分 | **+0.1** | 4.8 → **4.9** |
| #1 学习能力 | +0.225 | 2.0 → **3.5** — Gate C 真写入 + 1c 有界学习（env 非默认） |
| #2 自适应阈值 | +0.05 | 4.0 → **4.5** — 1c Compressor C1–C6 |
| #10 数据闭环 | +0.05 | 5.0 → **5.5** — analysis→evolution + C2 eval |
| 未变 | — | #3/#4/#5/#6/#7/#8/#9 |

## 距 5.5 差距（诚实）

| # | 维度 | 现评 | 距目标 | 需什么 |
|---|------|:--:|:--:|------|
| 1 | 学习能力 | 3.5 | **3.5** | 生产默认进化肌肉 + 更广 policy/技能学习（非仅门闩开） |
| 8 | 意图理解 | 3.5 | **4.0** | IQ-EVO-47 规则 `IntentPredictor` 已接线（非 ML 全量） |
| 2 | 自适应阈值 | 4.5 | **3.0** | 全量 23 项或稳定 1c 生产默认 |

**过线粗算（未达成）：** 若 #1→5.0（+0.225）且 #10→6.0（+0.05）≈ **5.175**；仍须 #8 或 #2 上调才稳 ≥5.5 — Wave 7 刻意未虚标 #1。

**ISSUES #12：** resolved · documented exception 续期（Wave 7 closeout）。

## 证据链

- [`p2-long-iqevo-wave7-closeout.md`](./p2-long-iqevo-wave7-closeout.md)
- [`iqevo-gate-c-closeout.md`](./iqevo-gate-c-closeout.md) · [`iqevo-gate-c-staging-write-evidence.md`](./iqevo-gate-c-staging-write-evidence.md)
- [`p2-long-iqevo-wave7-1c-closeout.md`](./p2-long-iqevo-wave7-1c-closeout.md) · `tests/contract/test_horizon_iqevo_wave7_1c.py`
- bridge §4 · IQ-EVO-40～45 evolution_log 行

**Wave A 复评（2026-06-01 · WA-A11）：** 工程粒 A00～A12 闭合；**总分仍 4.9**（未虚标 5.5）。#8 接线见 [`wave-a-intent-nudge-evidence.md`](./wave-a-intent-nudge-evidence.md)；生产 Q2 见 [`iqevo-30`](./iqevo-30-feishu-smoke-evidence.md) **FAIL**。exception 续期 → [`wave-a-closeout.md`](./wave-a-closeout.md)。

**IQ 5.5 Phase2 复评（2026-06-01 · 三轨汇合）：**

| 变化 | 现评 | Δ 加权 | 依据 |
|------|:--:|:------:|------|
| #3 反馈收集 | **5.5** | +0.05 | Q5 生产 JSONL + env · [`iq-q5-production-closeout.md`](./iq-q5-production-closeout.md) |
| #8 意图理解 | **4.5** | +0.10 | 飞书 3P（③ traj `16e3735611f87e85`）· 仍非 ML IntentPredictor 全量 |
| #10 数据闭环 | **5.6** | +0.01 | state.db 回填 + search 索引 + baseline 可审计 |
| #1/#2 等 | 不变 | — | 进化 ok 率、生产默认 1c 未本轨解决 |

**Phase2 加权：** 在 4.875 基线上 +0.16 ≈ **5.04 → 记 5.0**（诚实，**未达 5.5**）· exception 续期 → [`iq-55-phase2-closeout.md`](./iq-55-phase2-closeout.md)。

**下一复评：** ≥5.5 需 #1 生产默认进化 + 周常 eval 抬 ok 率，或刘哥 §20.3 接受 **5.0 + exception** 档位。
