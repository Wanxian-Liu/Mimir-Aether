# IQ-EVO · 进化任务制门禁（真源）

**Date:** 2026-05-26  
**拍板：** 刘哥 — 不用日历观察，**做完表中任务**再进下一档。  
**挂接：** [`MIMIR_LIU_CURSOR_BRIDGE.md`](../MIMIR_LIU_CURSOR_BRIDGE.md) §1 · handoff [`2026-05-26-wave6-cursor-handoff.md`](../superpowers/plans/2026-05-26-wave6-cursor-handoff.md) §0

---

## 档位 A → staging `MIMIR_AUTO_EVOLVE=1`

| ID | 任务 | 完成标准 | 产物 | 状态 |
|----|------|----------|------|------|
| **A1** | session_search 基线 | 脚本/mimir_ops **1 次** exit 0 | `data/ops/session_search_baseline_7d.json` | [x] |
| **A2** | evolution eval | `run_evolution_eval.sh` **1 次** exit 0 | `data/evolution_eval/memory-retrieval-compare-*.json` | [x] |
| **A3** | search-first 审计 | **10 条**抽样表 + 违例率 | [`iqevo-31-search-first-audit.md`](./iqevo-31-search-first-audit.md) | [x] |
| **A4** | 飞书 3 场景 | **3 行**证据 | [`iqevo-30-feishu-smoke-evidence.md`](./iqevo-30-feishu-smoke-evidence.md) | [x] |
| **A5** | analysis 质量 | **10** artifact 抽查，误报 **≤2/10** | [`iqevo-a5-analysis-sample.md`](./iqevo-a5-analysis-sample.md) | [x] |
| **A6** | tier0 | `./run_ralph_tier0.sh` **3 连绿** | [`iqevo-gate-a6-tier0.md`](./iqevo-gate-a6-tier0.md) | [x] 2026-05-26 |

**A 全 [x]（2026-05-26）→** 允许在 **staging** `.env` 设 `MIMIR_AUTO_EVOLVE=1`（**生产仍为 0**）。刘哥 **2026-05-26** 确认 staging 开启。

---

## 档位 B → 讨论生产 AUTO_EVOLVE

| ID | 任务 | 完成标准 | 产物 | 状态 |
|----|------|----------|------|------|
| **B1** | 开前快照 | git tag + skills 基线 | tag `gate-b1-20260526` · `gate-b1-skills-baseline.tar.gz` | [x] |
| **B2** | 触发分析 | **5** 次 close 带 suggestion | `gate-b-pilot-evidence.json`（5/5） | [x] |
| **B3** | 写入发生 | ≥**3** suggestion，≥**1** SKILL 写 | pilot dir 5/5 writes | [x] |
| **B4** | 写入质量 | 每个改动 OK 或 revert | [`iqevo-gate-b-closeout.md`](./iqevo-gate-b-closeout.md) §B4 | [x] |
| **B5** | 回归 | tier0 **3 连绿** | closeout §B5 · **454+2** | [x] |
| **B6** | 行为冒烟 | baseline + health + eval 各 **1** OK | closeout §B6 | [x] |
| **B7** | 回滚演练 | 关 env → tier0 绿 → 恢复 staging | closeout §B7 · Gateway **401777** | [x] |

**B 全 [x]（2026-05-26）→** staging 已开 `MIMIR_AUTO_EVOLVE=1`；**档位 C 已 [x]（2026-05-26）** — 本 home 生产 `MIMIR_AUTO_EVOLVE=1` 见 [`iqevo-gate-c-closeout.md`](./iqevo-gate-c-closeout.md)。

**执行 Wave 7：** [`p2-long-iqevo-wave7-gate-cd-plan.md`](./p2-long-iqevo-wave7-gate-cd-plan.md) · handoff [`2026-05-26-wave7-gate-cd-handoff.md`](../superpowers/plans/2026-05-26-wave7-gate-cd-handoff.md)

---

## 档位 C → 生产 AUTO_EVOLVE（可选）

| ID | 任务 | 完成标准 | 状态 |
|----|------|----------|------|
| **C1** | B 全过 | 见上 | [x] |
| **C2** | eval 累计 | 生产开启后 **3 次** eval exit 0（非 14 天日历） | [x] |
| **C3** | 无 P0 | 无技能改坏类 ISSUES P0 | [x] |

**C 全 [x]（2026-05-27）→** 本 home `MIMIR_AUTO_EVOLVE=1` 已拍板结案；产物 [`iqevo-gate-c-closeout.md`](./iqevo-gate-c-closeout.md) · §41 [`iqevo-gate-c-staging-write-evidence.md`](./iqevo-gate-c-staging-write-evidence.md)。

---

## 档位 D → Unified Plan **1c** 实现授权

| ID | 任务 | 完成标准 |
|----|------|----------|
| **D1** | Spike | 1 页 DecisionRing + Compressor 边界 | [x] |
| **D2** | 与 1b 分界 | 明文：1c 不写 SKILL、不替代 Top-3 tuner | [x] |
| **D3** | 契约草案 | ≥**5** 条拟新增 contract | [x] |
| **D4** | 刘哥签字 | bridge §1 一行 | [x] 2026-05-27 |

**D 全 [x]（2026-05-27）→** 已授权 1c 代码工程（IQ-EVO-43～45）；env `MIMIR_AUTO_1C_POLICY` **默认关**。
