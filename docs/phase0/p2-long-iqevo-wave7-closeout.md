# P2-LONG-IQEVO · Wave 7 closeout（Gate C/D + rubric #6）

**Date:** 2026-05-27  
**Grain:** IQ-EVO-46 / §50  
**Prior:** Wave 6 rubric **4.8/10** documented exception  
**tier0:** **466+2** PASS（`run_ralph_tier0.sh` · IQ-EVO-46 验收 1×）

---

## Rubric 复评 #6

| 项 | 值 |
|----|-----|
| **总分** | **4.9/10**（加权 **4.875**） |
| **相对 4.8** | **+0.1** |
| **≥5.5** | **否**（差 **0.6**） |
| **documented exception** | **是** |
| **真源** | [`iq-scoring-rubric.md`](./iq-scoring-rubric.md) |

### 主瓶颈（exception 理由）

1. **#1 学习能力 3.5**（权 15%）— Gate C/1c 已 **可开** 但 `MIMIR_AUTO_1C_POLICY` 默认关、进化非「每日默认肌肉」。
2. **#8 意图理解 3.5** — 仍无生产 IntentPredictor（Wave 6 离线 MVP 未抬）。

### 是否建议 §51 Intent

**否（本波不启动）** — 主瓶颈为 **#1 + 行为习惯**，非单独 #8；`IQ-EVO-47` 保留 backlog **[ ]**，须刘哥另拍板。

---

## 颗粒表（§40～§46）

| ID | 任务 | 状态 | 证据 |
|----|------|------|------|
| IQ-EVO-40 | analysis→evolution 时序 | [x] | `apply_evolution_from_analysis` · post_close tail · tier0 |
| IQ-EVO-41 | staging 真实 SKILL 写入 | [x] | `iqevo-gate-c-staging-write-evidence.md` · `skills/iqevo-41-gate-c-staging/` |
| IQ-EVO-42 | Gate C 结案 | [x] | `iqevo-gate-c-closeout.md` · C2 3× eval · `MIMIR_AUTO_EVOLVE=1` |
| GATE-D1 | 1c spike | [x] | `decision-ring-compressor-1c-spike.md` |
| GATE-D2 | 1c 边界 | [x] | `iqevo-1c-boundary.md` |
| GATE-D3 | contract 草案 | [x] | `iqevo-1c-contract-draft.md` · 1C-01～07 |
| GATE-D4 | 刘哥签字 | [x] | bridge §1 · 2026-05-27 |
| IQ-EVO-43 | 1c DecisionRing | [x] | `decision_compressor_policy.py` · 1C-01/02 |
| IQ-EVO-44 | 1c Compressor | [x] | C1–C6 · 1C-04/05 |
| IQ-EVO-45 | 1c contract 全量 | [x] | 1C-01～07 · `p2-long-iqevo-wave7-1c-closeout.md` · tier0 3× |
| IQ-EVO-46 | rubric #6 + 本 closeout | [x]（工程） | 战略窗 backlog 行由刘哥勾 |
| DOC-01 | 文档对齐 | [x] | bridge §5 · MAINLINE C 行 · 去「仍关 EVOLVE」过时表述 |
| IQ-EVO-47 | Intent MVP | [ ] | 可选 · 未开 |

---

## Gate C 摘要

| 项 | 结果 |
|----|------|
| C1 | 档位 B 全 [x] |
| C2 | `run_evolution_eval.sh` 3× exit 0（`~/.mimiraether`） |
| C3 | 无技能改坏 P0 |
| 生产 env | `MIMIR_AUTO_ANALYSIS=1` · `MIMIR_AUTO_EVOLVE=1` |

## Gate D 摘要

| 项 | 结果 |
|----|------|
| D1–D3 | spike · boundary · 7 contracts |
| D4 | 刘哥签字 2026-05-27 |
| 1c env | `MIMIR_AUTO_1C_POLICY` **默认关**（`1C-06`） |

---

## 工程纪律

| 检查 | 结果 |
|------|------|
| tier0 manifest | `test_horizon_iqevo_wave7_1c.py` 已在 `run_ralph_tier0.sh` |
| B-4 顺序 | tune → 1c；post_analysis defer + tail |
| M6 | IQ-EVO-40～45 已记 `evolution_log.md`；#46 文档粒可选 |

---

## 已知限制（carry）

- 1c / ring policy：**新 session** 才加载 JSON 变更。
- 1b 同 close 写 `compressor.threshold_percent` → 跳过激进 C3/C5。
- Rubric 仍低于 **5.5** → Horizon 续 **#1 / #8**，非再堆 tier0。

---

## Next

- **战略窗：** IQ-EVO-46 → [x]；Wave 7 工程 **[x]**（剩 **IQ-EVO-47** 可选）。
- **智商线：** #1 生产默认进化习惯 · 或 IQ-EVO-47 Intent（另拍板）。
