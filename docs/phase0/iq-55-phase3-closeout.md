# IQ 5.5 · Phase3 closeout（2026-06-01）

> **拍板**：§20.3 **IQ-RUBRIC-55-PHASE3** ✅  
> **出口**：rubric **≥5.5** 或 **documented exception**  
> **结论**：工程 **闭合** · rubric **~5.1** · **exception 续期**（未达 5.5）· 进化链 **P3-11 已修** · 生产 ok% **待部署后复测**

## 粒完成度

| ID | 状态 | 要点 |
|----|:----:|------|
| IQ-P3-00 | [x] | `iq_p3_evolution_ok_baseline.py` · `data/ops/iq-p3-baseline.json` · eval **3× exit 0** |
| IQ-P3-10 | [x] | [`iq-p3-evolution-failure-audit.md`](./iq-p3-evolution-failure-audit.md) |
| IQ-P3-11 | [x] | `DEPRECATE` · FIX→CAPTURED · `skills_root` · evolution detail log · tier0 **676** |
| IQ-P3-12 | [x] | 契约复测 PASS · 历史 log **不回溯** · 部署后复测 recipe 见 audit |
| IQ-P3-20 | [x] | env：`ANALYSIS/EVOLVE/TUNER/FEEDBACK=1` · **无** `AUTO_1C_POLICY` |
| IQ-P3-30 | [x] | 飞书 **3P 维持** Phase2 证据（③ `16e3735611f87e85`）· 无新 DM 本轮 |
| IQ-P3-31 | [x] | 本文件 + rubric Phase3 段 |

## P3-00 / P3-12 度量（诚实）

| 口径 | 7d 行数 | ok% | 说明 |
|------|--------:|----:|------|
| **排除测试 session** | 11 | **0.0** | 生产真实行修复前几乎全 `ok=0` |
| **含测试 session** | 128 | **60.9** | tier0 `iq07-sess` 等污染 · **勿用于宣称** |

**P3-11 后**：需 Gateway 加载新代码 + 新 close 样本；再跑 `iq_p3_evolution_ok_baseline.py` 验 **+10pp 或 ≥65%**。

## §1.5 终态

| # | Phase3 后 | 说明 |
|---|-----------|------|
| Q1 | **~5.1** + exception | #1 **4.0**（路径修通 + eval，无生产 ok% 提升证据） |
| Q2 | **PASS** | 3P 无回退 |
| Q3 | **PASS** | eval 3× · `memory-retrieval-compare-20260531T204957Z.json` |
| Q4 | **PASS** | tool_quality_weekly 2026-06-01 |
| Q5–Q7 | **PASS** | 继承 Phase2 |

**加权**：Phase2 **~5.0** + #1 部分抬升 **≈5.1** · **未达 5.5**

## 未达 5.5（exception 续期）

1. **#1**：历史生产 ok%=0；修复已合并但 **无部署后 7d ok%** 达 P3-12 阈值。  
2. **#8**：维持 **4.5**（规则 Intent · 3P），未上 ML。  
3. **#2**：1c 生产 **刻意未开**（刘哥拍板）。

## 运维（§20.2）

| ID | 状态 |
|----|------|
| OPS-EVAL-WEEKLY | [x] 2026-06-01 · 3× exit 0 |
| OPS-MW-REFRESH | [x] 2026-06-01 · TRUNCATE=0 · health quick 曾 timeout（网关进程在） |
| CLR-B-FEISHU | [ ] 刘哥 · 可下一轮顺带 |

## 证据索引

- [`iq-p3-evolution-failure-audit.md`](./iq-p3-evolution-failure-audit.md)  
- [`iq-55-phase3-execution-plan.md`](./iq-55-phase3-execution-plan.md)  
- [`iq-scoring-rubric.md`](./iq-scoring-rubric.md) · Phase3 复评行
