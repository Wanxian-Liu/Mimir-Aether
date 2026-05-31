# Wave B · WM Phase0 spike — 工程粒与 Cursor 新窗提示词

> **拍板**：§20.3 **WM-HORIZON-01** ✅（2026-05-31）  
> **真源**：[`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md) · [`world-model-agent-handoff.md`](../superpowers/plans/2026-05-27-world-model-agent-handoff.md) §7  
> **前置**：Wave A 已 closeout（[`wave-a-closeout.md`](./wave-a-closeout.md)）· rubric **4.9 + exception**  
> **出口**：`wm-phase0-spike-closeout.md` · **禁止** 与 Horizon C / Wave A 补救（A06.1）**混 PR**

**Phase 0 spike 定义（刘哥拍板 · 非全文 Phase 1～3）**

- **要**：可测的最小竖切 — **表征预测 MVP（规则/桩）** + **VoE→学习 接线设计**（surprise 不只告警）  
- **不要**：像素世界模型 · 生产 gateway 默认全开 · 分层规划全量 · 与 §19.1 Horizon C 粒混在同一 PR

---

## 0. 谁执行？

| 执行面 | Wave B |
|--------|--------|
| **Cursor 新窗** | **默认** — 读代码、写 spike 文档/桩模块、tier0、独立分支 PR |
| **Mimir** | 可选只读验收；**不**替代 Cursor 写 spike |
| **刘哥** | 拍板范围变更；非每粒必在 |

---

## 1. 工程粒总表（按序）

| 序 | ID | 任务 | 成功标准 | 状态 |
|:--:|-----|------|----------|:----:|
| 0 | **WB-B00** | **钉死 spike 范围 + 代码地图** | `wm-phase0-spike-scope.md`（含 in/out · 依赖 · WB-B01 验收） | [x] |
| 1 | **WB-B01** | **WorldModelPredictor 规则 MVP** | `agent/world_model_spike.py`（或同名）+ 单测 · 输入 context → `Prediction(needs, skills, expected)` | [x] |
| 2 | **WB-B02** | **VoE→学习 最小接线** | surprise 路径 → 写 memory/JSONL **事件**（或 documented stub + contract）· 单测 | [x] |
| 3 | **WB-B03** | **tier0 + M6 + closeout** | `./run_ralph_tier0.sh` PASS · `wm-phase0-spike-closeout.md` · bridge §4 | [x] |

**并行禁止**：WB-B01 与 WB-B02 可同窗若极小；**禁止** 与 `degeneration_guard` 大重构同 PR。

---

## 2. 新窗口提示词（按序复制）

### 窗口 0 · Cursor — WB-B00（第一窗 · 只做本粒）

```text
【角色】Cursor 新窗 · MimirAether · Wave B · WM Phase0

【Superpowers】using-superpowers → verification-before-completion（本窗以文档+地图为主，无代码也可完成）

【必读 · 按顺序】
1) docs/proposals/world-model-evolution-plan.md — §1 已有/缺失 · §2 架构图 · §3.1 Surprise→学习（P1 VoE）
2) docs/superpowers/plans/2026-05-27-world-model-agent-handoff.md — §1 战略 · §7 路线图
3) docs/phase0/wave-a-closeout.md — Wave A 出口（4.9·Q2 部分）· 勿混本 PR
4) agent/degeneration_guard.py — surprise_gate 现有行为（告警 vs 学习）
5) docs/phase0/wave-b-execution-plan.md — 本表 WB-B00～B03

【本窗 · WB-B00 唯一交付】
新建 docs/phase0/wm-phase0-spike-scope.md，须包含：
- **Spike 一句话**：LLM 世界模型在 Mimir 的 Phase0 竖切是什么（规则 MVP 预测器 + VoE 学习事件最小路径）
- **In scope（WB-B01/B02）**：列 2～3 个可验证条目（含文件路径意向）
- **Out of scope**：Horizon C · Wave A/A06.1 · Phase 1.2 分层规划全量 · 改 SESSION_SEARCH 生产默认 · gateway 默认接线
- **代码地图**：degeneration_guard / surprise_gate / memory 写路径 / intent_predictor（仅引用，不重构）
- **WB-B01 验收**：pytest 命令 + 期望断言类型
- **WB-B02 验收**：surprise 触发后何种持久化（字段/schema）· 如何单测（mock 即可）
- **风险**：与 Wave A「search-first 行为未过线」的关系（WM 不替 A 还债）

【禁止】
- 本窗不写 agent/ 生产接线（留给 B01/B02）
- 不要混 Horizon C / OPS / IQ-EVO 日常粒
- 不要 commit data/persistent.json
- 不要宣称 rubric 已达 5.5

【仓库】~/src/MimirAether · MIMIR_AETHER_HOME=~/.mimiraether

【回报】
- 贴 wm-phase0-spike-scope.md 路径
- bridge §4 一行：WB-B00 spike scope locked · next WB-B01
- 更新 wave-b-execution-plan.md 表 WB-B00 → [x]
```

### 窗口 1 · Cursor — WB-B01（scope 锁定后再开）

```text
【角色】Cursor 新窗 · Wave B · WB-B01

【前置】wm-phase0-spike-scope.md 已 [x] · 按其中 WB-B01 验收实现

【本窗】规则 MVP：agent/world_model_spike.py（名以 scope 为准）
- dataclass：Prediction（next_context_needs / applicable_skills / expected_outcome 等，对齐 plan §2 图）
- predict(context_snapshot) -> Prediction（规则/heuristic，不调 LLM API）
- tests/agent/test_world_model_spike.py

【验证】./run_ralph_tier0.sh · 触达 agent/ 则 ./scripts/record_m6_evolution.sh 一行

【禁止】gateway 接线 · VoE 写 memory（WB-B02）· Horizon C · 与 B02 混超大 PR

【回报】bridge §4：WB-B01 predictor MVP + tier0
```

### 窗口 2 · Cursor — WB-B02

```text
【角色】Cursor 新窗 · Wave B · WB-B02

【前置】WB-B01 [x] · 读 scope 中 VoE→学习 设计

【本窗】最小接线：surprise_gate 触发 → 持久化 surprise 事件（memory 或 $MIMIR_AETHER_HOME/data/…，以 scope 为准）
- 最小 diff degeneration_guard 或旁路 hook（勿大重构）
- 单测：mock surprise → 断言写入

【禁止】生产默认全开 · 混 WB-B01 重做

【回报】bridge §4：WB-B02 VoE learning wire + tier0
```

### 窗口 3 · Cursor — WB-B03 closeout

```text
【角色】Cursor 新窗 · Wave B · WB-B03

【本窗】docs/phase0/wm-phase0-spike-closeout.md · tier0 全绿 · M6 · bridge §4 · wave-b-execution-plan B01～B03 [x]

【出口陈述】Phase0 spike 完成了什么、明确没做什么、与 Phase 1.1 的差距

【禁止】顺手做 Phase 1.2+ · 与 Horizon C 混 PR
```

---

## 3. Wave B 完成后

- 是否开 **Phase 1.1**（surprise→学习生产化）→ 刘哥另批，新 Wave / 新 PR  
- Wave A 未还债：**A06.1** search 守卫 — **独立 PR**，不塞进 Wave B
