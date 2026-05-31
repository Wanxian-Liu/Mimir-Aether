# IQ 5.5 · Phase2 三轨汇合（2026-06-01）

> **计划**：IQ 5.5 Q5 / 索引·记忆 / Wave B（staging + replan）  
> **结论**：三轨工程 **闭合** · 飞书 **3P** · rubric **~5.0** · **exception 续期**（未达 5.5）  
> **战役 A（刘哥拍板）**：**2026-06-01 正式收官** · 出口 **5.0 + documented exception** · **Phase3（冲 ≥5.5）待 §20.3 另开**

## 轨完成度

| 轨 | Closeout | 状态 |
|----|----------|:----:|
| Q5 | [`iq-q5-production-closeout.md`](./iq-q5-production-closeout.md) | **PASS** |
| 2a 索引 | [`iq-idx-closeout.md`](./iq-idx-closeout.md) | **PASS**（含 ③ DM **PASS**） |
| 2b memory | 本表 + `tests/tools/test_memory_discover_fallback.py` | **PASS** fallback |
| 3 WM | [`wm-p11-staging-closeout.md`](./wm-p11-staging-closeout.md) | **PASS** |
| tier0 | `./run_ralph_tier0.sh` | **674 PASS** |

## §1.5 对照（Phase2 后）

| # | Phase2 后 | 说明 |
|---|-----------|------|
| Q1 | **~5.0** + exception | 见 [`iq-scoring-rubric.md`](./iq-scoring-rubric.md) Phase2 段 |
| Q2 | **PASS** | 飞书 ①②③ **3P**（③ traj `16e3735611f87e85` · 2026-06-01 刘哥复测） |
| Q3–Q4 | **PASS** | 无变 |
| Q5 | **PASS** | JSONL + env |
| Q6–Q7 | **PASS** | 无变 |

## 为何仍未 ≥5.5（诚实）

1. **#1 学习能力**：WM prompt 接线 ≠ 生产默认进化肌肉；进化 log ~52% ok 未本轨解决。  
2. **#8 意图理解**：冒烟 **3P** 已签收，但仍是规则 IntentPredictor，非 ML 全量。  
3. **#2 自适应**：1c/AutoTuner 生产默认仍关。

未达 5.5 的缺口留给 **Phase3**（若刘哥后续拍板 B）：#1 生产默认进化肌肉 + 周常 eval 抬 ok 率。

## 战役 A 收官（刘哥 · 2026-06-01）

| 项 | 裁定 |
|----|------|
| **工程** | PR **#40–#42** 已合并 `main`（`bdf42ab`） |
| **行为** | 飞书 ①②③ **3P** · Q5/Q2/Q6–Q7 **PASS** |
| **分数** | rubric **~5.0** · **不追本战役内 ≥5.5** |
| **exception** | **续期** · 理由见上节 |
| **Phase3** | **已开**（2026-06-01 · §20.3 **IQ-RUBRIC-55-PHASE3**）→ [`iq-55-phase3-execution-plan.md`](./iq-55-phase3-execution-plan.md) |

**合并后运维（Mimir，非 Cursor）**：`git pull` · `ensure_single_gateway.sh` · 生产 seed + backfill（见 [`iq-idx-closeout.md`](./iq-idx-closeout.md) 复验命令）。

## PR 边界（已遵守）

- `feat/iq-idx-01`：backfill/seed/gateway/session + idx closeout  
- `feat/iq-mem-01`：discover fallback + tests  
- `feat/wm-p11-ops`：wm pending prompt + tests + wm closeout  
- docs 汇总：本文件 + rubric/bridge/wave-a 行更新

## 证据索引

- [`iqevo-30-feishu-smoke-evidence.md`](./iqevo-30-feishu-smoke-evidence.md)  
- [`wave-a-closeout.md`](./wave-a-closeout.md)（Q5/基线行已更新）  
- Bridge §4 · **IQ-55-PHASE2** 行
