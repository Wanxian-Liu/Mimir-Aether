# P2-LONG-IQEVO · Wave 7 · 1c closeout（IQ-EVO-43～45）

**Date:** 2026-05-24  
**Grain:** IQ-EVO-45 / §49 — contract 全量 + 工程 closeout  
**tier0:** **466+2** PASS · `run_ralph_tier0.sh` 连续 3× exit 0（2026-05-24）

## Summary

| Grain | Scope | Status |
|-------|--------|--------|
| IQ-EVO-43 | `decision_compressor_policy.py` + `decision_ring` policy merge；B-4 defer + post_analysis tail | [x] |
| IQ-EVO-44 | Compressor C1–C6 bounds + ≤2 nudges/close；1b/C3/C5 屏蔽 | [x] |
| IQ-EVO-45 | Contract **1C-01～07** + §49 接线清单 + 本 closeout | [x] |

**Env（默认关）：** `MIMIR_AUTO_1C_POLICY` — 未设或非 `1` 时 `run_1c_policy_after_pipeline_close` 不写 `decision_compressor_policy.json`（`1C-06`）。

**持久化：** `$MIMIR_AETHER_HOME/data/decision_compressor_policy.json` + `data/audit/decision_compressor_policy.jsonl`（D3 锁定名）。

## Contract IDs（pytest）

| ID | Test | Assert |
|----|------|--------|
| 1C-01 | `test_1c_never_writes_skill_md` | 模块无 skill evolution / `SKILL.md` 写入 |
| 1C-02 | `test_1c_rejects_top3_keys_in_policy` | Top-3 ring keys 拒绝 |
| 1C-03 | `test_1c_never_calls_set_override` | 1c 路径不调用 `set_override` |
| 1C-04 | `test_1c_policy_bounds_reject_out_of_range` | D*/C* 越界拒绝 |
| 1C-05 | `test_1c_at_most_two_nudges_per_close` | 每 close ≤1 D* + ≤1 C* |
| 1C-06 | `test_1c_env_gate_off_by_default` | 无 env 不写 policy |
| 1C-07 | `test_1c_and_evolve_disjoint_persistence` | 不碰 `skills/`、`tuned_thresholds.json` |

**接线：** `test_1c_b4_close_chain_wiring`（defer + `run_tune_and_1c_after_post_analysis`）；`test_wave7_1c_contract_in_tier0`。

**真源：** `docs/phase0/iqevo-1c-contract-draft.md` · `iqevo-1c-boundary.md` · `decision-ring-compressor-1c-spike.md`

## Gate D（iqevo-evolution-gates.md）

| Step | Status |
|------|--------|
| D1 spike | [x] |
| D2 boundary | [x] |
| D3 contract draft | [x] |
| D4 刘哥签字 | [x] 2026-05-27 |

## B-4 close 顺序

1. **无 post_analysis：** `execution_pipeline.close` → `run_tune_after_pipeline_close` → `run_1c_policy_after_pipeline_close`
2. **有 post_analysis：** tune+1c **defer** → `post_close_analysis` tail → `run_tune_and_1c_after_post_analysis`（先 1b 再 1c）

## 已知限制

- **新 session：** policy 在 agent 构造时 merge 进 `DecisionRing` / compressor；运行中改 policy 文件需新 session 才生效。
- **1b 同 close：** 若 1b 已写 `compressor.threshold_percent`，当次跳过激进 **C3/C5** nudge（IQ-EVO-44）。
- **EVOLVE 并行：** 可与 1c 同 close；三者持久化路径不重叠（B-1/B-3）；`1C-07` 断言 1c 不越界。

## Next（战略窗，非本粒）

- **§50 / IQ-EVO-46：** rubric #6 + Wave 7 closeout
