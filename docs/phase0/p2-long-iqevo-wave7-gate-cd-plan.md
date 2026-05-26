# P2-LONG-IQEVO · Wave 7（Gate C/D + 智商 ≥5.5）

**Date:** 2026-05-26  
**拍板：** 刘哥 — 「C、D、提高智商都同意；先完善计划，新窗按提示词做」  
**Baseline:** Wave 6 结案 · rubric **4.8/10**（距 **5.5** 差 **0.7**）· Gate **A/B [x]** · staging `MIMIR_AUTO_EVOLVE=1`  
**真源：** [`iqevo-evolution-gates.md`](./iqevo-evolution-gates.md) 档位 C/D · Unified Plan **1c** · [`MIMIR_UNIFIED_PLAN.md`](../MIMIR_UNIFIED_PLAN.md) 冲突 3  
**Handoff（新窗粘贴）：** [`docs/superpowers/plans/2026-05-26-wave7-gate-cd-handoff.md`](../superpowers/plans/2026-05-26-wave7-gate-cd-handoff.md)

---

## 1. 目标（可验证）

| 目标 | 完成判据 |
|------|----------|
| **Gate C** | C1–C3 全 [x]；生产（`$MIMIR_AETHER_HOME`）`MIMIR_AUTO_EVOLVE=1`；**≥1 次真实** SKILL 写入且人工 OK；`run_evolution_eval.sh` **3×** exit 0 |
| **Gate D** | D1–D4 全 [x]；刘哥 bridge §1 **签字行**；**才**允许 1c 代码 |
| **智商 ≥5.5** | rubric 复评 #6 · 加权 **≥5.5** 或 **documented exception** 写明剩余差距 + 下一 Horizon |
| **工程纪律** | 每粒 `./run_ralph_tier0.sh` 绿；触达 agent/gateway/tools → `record_m6_evolution.sh`；**不**提交 `data/persistent.json` |

---

## 2. 依赖链（必须按序）

```text
§39 文档对齐（可选首粒）
  ↓
§40 修 analysis → evolution 时序（阻塞一切 AUTO_EVOLVE 真效果）
  ↓
§41 staging 真实 SKILL 写入证据
  ↓
§42 Gate C 生产 AUTO_EVOLVE + 3× eval + closeout
  ↓
§43–§45 Gate D 文档（D1 spike · D2 分界 · D3 contract 草案）
  ↓
§46 刘哥 D4 签字（人工 · bridge §1 一行）
  ↓
§47–§49 Unified Plan 1c 实现（有界 · 不写 SKILL）
  ↓
§50 rubric 复评 #6（目标 5.5）
  ↓
§51（可选）Intent 生产 MVP — 仅当 §50 仍 <5.5 且 #8 为主瓶颈
```

**禁止并行：** §47–§49 与 §42 之前不得在生产开 AUTO_EVOLVE；§47–§49 不得在 **§46 签字前** 写 1c 代码。

---

## 3. 智商路径（数学与工程对应）

当前加权 **4.75 → 4.8**（[`iq-scoring-rubric.md`](./iq-scoring-rubric.md)）。

| 维度 | 权 | 现 | 目标（过 5.5） | Wave 7 杠杆 |
|------|:--:|:--:|:--:|-------------|
| **#1 学习能力** | 15% | 2.0 | **≥5.0** | Gate C 真实 SKILL 进化 + 1c 有界策略/压缩学习 |
| **#10 数据闭环** | 10% | 5.0 | **≥6.0** | analysis → evolution → 行为/技能 闭合（§40） |
| **#8 意图理解** | 10% | 3.5 | **≥5.0** | §51 可选；非首路径 |
| **#2 自适应阈值** | 10% | 4.0 | **≥5.0** | 1c Compressor 有界自适应（不替代 1b Top-3） |

**粗算：** #1: 2→5 (+0.45) + #10: 5→6 (+0.10) + #8: 3.5→5 (+0.15) ≈ **5.35**；需 #1 更高或 #2/#5 小幅上调才稳 **≥5.5**。

---

## 4. 颗粒表（backlog §15 Wave 7）

| ID | 任务 | Owner | 成功标准 | 状态 |
|----|------|-------|----------|------|
| **DOC-01** | bridge/backlog/gates/MAINLINE 过时段对齐 | Cursor | 无「下一档 B」「仍关 staging EVOLVE」矛盾 | [ ] |
| **IQ-EVO-40** | **analysis → evolution 时序修复** | Cursor | 单测：async analysis 完成后 SKILL 写入；tier0 | [ ] |
| **IQ-EVO-41** | **staging 真实写入证据** | Cursor+Mimir | `~/.mimiraether/skills/` ≥1 次非 pilot 写入 + 审查 OK | [ ] |
| **IQ-EVO-42** | **Gate C 结案** | Cursor+刘哥 | C2 3× eval；`iqevo-gate-c-closeout.md`；Gateway 重启 | [ ] |
| **GATE-D1** | DecisionRing + Compressor **1c Spike**（1 页） | Cursor | `decision-ring-compressor-1c-spike.md` | [ ] |
| **GATE-D2** | **1c 与 1b 分界**明文 | Cursor | 同上或独立节：不写 SKILL · 不替代 Top-3 | [ ] |
| **GATE-D3** | **≥5 条**拟新增 contract | Cursor | 清单 + 对应 pytest 文件名 | [ ] |
| **GATE-D4** | **刘哥签字** | 刘哥 | bridge §1 一行授权 1c | [ ] |
| **IQ-EVO-43** | 1c · DecisionRing **有界**策略学习 | Cursor | 仅配置/权重有界；tier0 | [ ] |
| **IQ-EVO-44** | 1c · Compressor **有界**自适应 | Cursor | 与 `tuned_thresholds` 正交；tier0 | [ ] |
| **IQ-EVO-45** | 1c tier0 contract + closeout 草案 | Cursor | `test_horizon_iqevo_wave7_1c.py` | [ ] |
| **IQ-EVO-46** | rubric **复评 #6** + Wave 7 closeout | Mimir+Cursor | **≥5.5** 或 documented exception | [ ] |
| **IQ-EVO-47** | （可选）Intent 生产 MVP | Cursor | 仅 §46 后且 #8 仍卡 5.5 | [ ] |

---

## 5. §40 技术要点（analysis → evolution）

**现状 bug：** `agent_loop._close_pipeline` 顺序为：

1. `close_execution_pipeline()` — session 已 pop  
2. `schedule_post_close_analysis()` — **异步** LLM → `apply_analysis_to_pipeline()`（此时常无 session）  
3. `schedule_post_close_evolution(result)` — **同步**，close 时 `_evolution_suggestion_objs` 常为空  

**验收：** 在 `MIMIR_AUTO_ANALYSIS=1` + `MIMIR_AUTO_EVOLVE=1` 下，带 `errors`/`degraded_tools` 的 close → analysis 产出 `fix` suggestion → **SKILL 文件变更**（非 pilot 目录）。

**实现方向（择一，handoff §40 内定）：**

- **A（推荐）：** analysis worker 末尾：若有 suggestions → 直接 `apply_evolution_from_suggestions_async` 或 `schedule_post_close_evolution` 传入含 objs 的 dict  
- **B：** close 前同步跑 `run_post_analysis_sync`（仅当 env 双开且 has signal）— 阻塞略增  

**测试：** 扩展 `tests/agent/test_evolution_loop_integration.py` 或新增 parity 测 async 路径。

---

## 6. Gate C 运维（刘哥机单 home）

本机 **`MIMIR_AETHER_HOME=~/.mimiraether`** 即 staging/生产同 home。Gate C「生产」= **在该 home 上完成 §41 证据后保持 `MIMIR_AUTO_EVOLVE=1`**，不是第二套机器。

| 步骤 | 动作 |
|------|------|
| C1 | B 全 [x]（已满足） |
| C2 | §42 后连续 **3 次** `./scripts/run_evolution_eval.sh` exit 0，路径写入 closeout |
| C3 | 审查 SKILL 改动；无 P0；ISSUES 无「技能改坏」新条 |
| 回滚 | `MIMIR_AUTO_EVOLVE=0` + `restart_gateway_hard.sh` + `gate-b1-skills-baseline.tar.gz` 恢复 |

---

## 7. Gate D / 1c 边界（D2 必须明文）

| 允许（1c） | 禁止（1c） |
|----------|------------|
| DecisionRing **策略权重/阈值**有界学习（来自 feedback/tune 信号） | 写/改 **SKILL.md**（属 AUTO_EVOLVE / E-009） |
| Compressor **threshold_percent** 等在 1b 边界外的**第二档**有界旋钮 | 替代 **Top-3** AutoTuner 键 |
| 新 contract 测 + evolution_log | 无界自改 `degeneration_guard.json` 源文件 |
| 消费 Wave 4/5 JSONL，只读 artifact 摘要 | 全量 IntentPredictor（属 §51 可选） |

**模块 touch 表（D1 spike 须填）：** `agent/decision_ring.py` · `agent/context_compressor/` · `agent/recovery_mixin.py` · `agent/core_loop.py`（compressor 构造）

---

## 8. Mimir 角色（飞书）

| 粒 | Mimir |
|----|-------|
| §41 | 可选：制造 1 次真实 degraded close；回报 artifact 路径 + skill 路径 |
| §42 | 确认生产 AUTO_EVOLVE 后飞书 1 轮正常 |
| §46 | **刘哥** bridge 签字；Mimir **勿**代签 |
| §50 | rubric 复评（提案轨 A）；bridge §4 一行 |

**Mimir 勿：** 在 §46 前改 agent/gateway 做 1c；勿并行 Hermes 大 diff 研究（暂停至 Wave 7 结案）。

---

## 9. ISSUES / bridge 现状（2026-05-26）

| 来源 | 未完成 |
|------|--------|
| `MIMIR_ISSUES.md` Active | 仅 **#3** deferred（ADR-002 设计债）— **不挡** C/D |
| `#12` | 已 resolved（Wave 6 exception） |
| `docs/ISSUES.md` #1 识图 | blocked（vision key）— 与 C/D 无关 |
| bridge §1/§5 | **文档债** — DOC-01 清 |

---

## 10. 完成定义（Wave 7 整波）

- [ ] `iqevo-evolution-gates.md` 档位 **C、D** 全 [x]  
- [ ] `p2-long-iqevo-wave7-closeout.md` + rubric **≥5.5** 或 exception  
- [ ] tier0 **454+2**（或当时 manifest）**3 连绿** 在 Wave 7 最后一粒  
- [ ] bridge §4 每粒一行 + §1 档位 C/D 状态更新  
- [ ] `MAINLINE_STATUS.md` 最近更新 + Wave 7 摘要  

---

## 11. 新窗用法

1. 打开 [`2026-05-26-wave7-gate-cd-handoff.md`](../superpowers/plans/2026-05-26-wave7-gate-cd-handoff.md)  
2. **每个新 Cursor 对话**：粘贴 **§0 + 一个 §N**（严格顺序，勿跳 §40）  
3. 粒完成后 agent 标 backlog `[x]`、更新 gates 表、bridge §4  

**刘哥：** §46 收到 D1–D3 后，在 bridge §1 粘贴 handoff 里 **GATE-D4 签字模板**。
