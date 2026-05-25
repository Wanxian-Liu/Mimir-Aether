# P2-LONG-IEVO — Wave E 结案（IEVO-06）

> **日期**：2026-05-25  
> **母任务**：`P0-LONG-CLEARANCE` §13.1 子阶段 **E**  
> **验证**：`./run_ralph_tier0.sh` → **322+2** PASS；可选 `./scripts/run_evolution_eval.sh`（本机 `sessions_search.db`）

## 工业进化 MVP（masterplan §6.2 / §0 D8）

| # | 要求 | 证据 |
|---|------|------|
| 1 | 禁伪进化（D5-1） | `agent/evolution_audit.py` + `tests/contract/test_no_simulated_evolution_ievo01.py`；`record_m6_evolution.sh` 拦截 |
| 2 | 可审计（M6） | `docs/evolution_log.md` + pre-push；Wave E 各行 `20260525T*` |
| 3 | 可测收益 | `scripts/run_evolution_eval.sh` + `compare_memory_retrieval_baseline.py`；基线 `docs/phase0/memory-retrieval-benchmark-20260524.json` |
| 4 | 可回滚 | STAB-05 · `tests/agent/test_evolution_rollback_stab05.py`（tier0） |
| 5 | ADR 真源（D6-1） | `docs/adr/005-observability-execution-sot.md` · `tests/contract/test_observability_sot_ievo03.py` |

## 子项对照

| ID | 摘要 | 状态 |
|----|------|------|
| IEVO-01 | D5-1 禁 `simulated:true` | [x] |
| IEVO-02 | D5-3 evolution pytest 入 tier0 | [x] |
| IEVO-03 | D6-1 ADR-005 ExecutionRecorder SoT | [x] |
| IEVO-04 | `run_evolution_eval.sh` + 基线对比 | [x] |
| IEVO-05 | D6-3 monitor/insights 回归 ≥3 | [x] |
| IEVO-06 | 本结案 + Phase ∞ §执行记录 | [x] |

## GitHub icebox（部分关 · 不 force-close）

| GH | 已交付 | 余量（仍 icebox） |
|----|--------|-------------------|
| **#21** | D5-1、D5-3、tier0 evolution 路径 | D5-ADR 双架构、真进化 wide 指标 |
| **#22** | D6-1 ADR-005、D6-3 回归测 | D6-2 ObservabilityBus |

## tier0 契约束（Gate2 须保持）

- `tests/contract/test_no_simulated_evolution_ievo01.py`
- `tests/contract/test_evolution_tier0_manifest_ievo02.py`
- `tests/contract/test_observability_sot_ievo03.py`
- `tests/contract/test_evolution_eval_ievo04.py`
- `tests/agent/test_ievo05_monitor_insights_regression.py`
- `tests/contract/test_monitor_insights_ievo05.py`
- `tests/contract/test_ievo06_wave_e_closeout.py`

## 下一粒

- **母任务**：`CLEARANCE-DONE`（§0 D1–D8 全绿 · 刘哥 sign-off）— 非本波工程自动完成。
