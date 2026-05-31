# IQ 5.5 · Phase3 — 进化 ok 率与 eval（2026-06-01）

> **拍板**：§20.3 **IQ-RUBRIC-55-PHASE3** ✅（刘哥 · 开 Phase3）  
> **前置**：战役 A **5.0 + exception**（[`iq-55-phase2-closeout.md`](./iq-55-phase2-closeout.md)）  
> **出口**：rubric **≥5.5** 或 **documented exception**（[`iq-scoring-rubric.md`](./iq-scoring-rubric.md)）  
> **禁止**：1c 生产（`MIMIR_AUTO_1C_POLICY`）· Phase2 三轨重开 PR · `SESSION_SEARCH`/`MIMIR_CROSS_SESSION_RAG`/`MIMIR_WM_VOE_*` 生产默认 · ML Intent 全量

---

## 0. 谁在哪执行？

| 执行面 | 做什么 | Phase3 里 |
|--------|--------|-----------|
| **Cursor 新窗** | 基线脚本、进化归因/修复、docs、tier0、PR | **IQ-P3-00～P3-12、P3-31** |
| **Mimir** | eval 周常、MW 刷新、env 核对 | **IQ-P3-20**、§20.2 |
| **刘哥（飞书）** | 3P 回归、CLR-B | **IQ-P3-30** |

**签收**：每粒 **bridge §4** 一行；粒表 `[x]` 在本文件。

---

## 1. 工程粒总表（按顺序 · 单线）

| 序 | ID | Owner | 任务 | 成功标准 | 状态 |
|:--:|-----|-------|------|----------|:----:|
| 0 | **IQ-P3-00** | Cursor | 基线包 | `iq_p3_evolution_ok_baseline.py` → `data/ops/iq-p3-baseline.json`；eval **3× exit 0** | [x] |
| 10 | **IQ-P3-10** | Cursor | 失败归因 | [`iq-p3-evolution-failure-audit.md`](./iq-p3-evolution-failure-audit.md) top-3 原因 | [x] |
| 11 | **IQ-P3-11** | Cursor | 最小修复 | `DEPRECATE` · FIX→CAPTURED · tier0 **676** | [x] |
| 12 | **IQ-P3-12** | Cursor | ok% 复测 | 契约 PASS · 部署后复测 recipe（历史 log 不回溯） | [x] |
| 20 | **IQ-P3-20** | Mimir+Cursor | 生产 env | `FEEDBACK/ANALYSIS/EVOLVE/TUNER=1` · 无 `AUTO_1C_POLICY` | [x] |
| 30 | **IQ-P3-30** | 刘哥+Mimir | 飞书 3P | Phase2 证据维持 · 无新 DM | [x] |
| 31 | **IQ-P3-31** | Cursor | rubric + closeout | **~5.1** + exception · 本 closeout | [x] |

**§20.2 并行（不挡上表）**：`OPS-EVAL-WEEKLY` · `OPS-MW-REFRESH` · `CLR-B-FEISHU`（刘哥）

---

## 2. 过线粗算（诚实）

Phase2 出口 **~5.0**。Phase3 主攻 **#1**（3.5→≥5.0）：进化 **ok%** + 周常 eval，**非**「已开 AUTO_EVOLVE」 alone。  
#8 维持 **4.5**（3P）；不追 ML。若 #1→5.0 加权约 **+0.225** → **~5.2**；稳 **≥5.5** 可能仍需 #8/#2 或 **exception**。

---

## 3. Cursor 新窗一句

```text
Read docs/phase0/iq-55-phase3-execution-plan.md 第一条 [ ]。
真源：iq-scoring-rubric.md Phase3 段 · MIMIR_IQ_EVOLUTION_DIRECTION.md §1.5。
每粒：./run_ralph_tier0.sh · bridge §4 一行 · 本表 [x]。
禁止：1c 生产 · idx/mem/wm 混 PR · SESSION_SEARCH 生产默认。
```

## 4. Mimir 新窗一句

```text
Read bridge §1 + backlog §20.2 第一条 [ ] + iq-55-phase3-execution-plan.md IQ-P3-20。
MIMIR_AETHER_HOME=~/.mimiraether · 回报 §3.3 + bridge §4。
禁止 push · 禁止改 agent|gateway|tools（代码 → ISSUES → Cursor P3-11）。
```
