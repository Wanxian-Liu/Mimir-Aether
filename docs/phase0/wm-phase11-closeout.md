# WM Phase 1.1 closeout（WM-P11-04）

> **日期**：2026-06-01  
> **前置**：Wave B Phase0 — [`wm-phase0-spike-closeout.md`](./wm-phase0-spike-closeout.md)  
> **真源**：[`wm-phase11-scope.md`](./wm-phase11-scope.md) · plan [`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md) §3.1  
> **执行表**：[`wm-phase11-execution-plan.md`](./wm-phase11-execution-plan.md) WM-P11-00～04

---

## 完成了什么

| 粒 | 交付 | 证据 |
|:--:|------|------|
| **WM-P11-00** | 1.1 范围 + 验收定义 | [`wm-phase11-scope.md`](./wm-phase11-scope.md) |
| **WM-P11-01** | surprise → **可 recall 学习库** | [`agent/wm_voe_learning.py`](../../agent/wm_voe_learning.py) · `lookup_learned_surprise` / `record_surprise_learning` · `$MIMIR_AETHER_HOME/data/wm_phase11/learned_surprises.json` · JSONL **双写** |
| **WM-P11-02** | replan **学习上下文** | [`degeneration_guard.py`](../../agent/degeneration_guard.py) · `report.details["wm_learning_context"]` · `MIMIR_WM_VOE_REPLAN_CTX` 默认 **0** |
| **WM-P11-03** | **第二次不 surprise** | recall **前置** · `MIMIR_WM_VOE_RECALL=1` · 同 pair 2nd → `CLEAN` · 抑制时 **不** append JSONL |
| **WM-P11-04** | 本文档 + tier0 复验 | `./run_ralph_tier0.sh` **665 PASS**（Gate3 2 PASS） |

### plan §3.1 对照

| 目标 | Phase 1.1 状态 |
|------|----------------|
| surprise → 可 recall 记忆 | ✅ `learned_surprises.json` index（Path C） |
| replan 带学习上下文 | ✅ `wm_learning_context` on report（消费方未强制 gateway 接线） |
| 同场景第二次不再 surprise | ✅ 精确 `(expected, actual)` lookup 抑制 |
| 生产默认 | ✅ 全部 `MIMIR_WM_*` 默认 **0** |

### Env 门控（生产默认）

| 变量 | 默认 | Phase 1.1 作用 |
|------|------|----------------|
| `MIMIR_WM_VOE_LEARNING` | `0` | JSONL audit + index 双写 |
| `MIMIR_WM_VOE_RECALL` | `0` | lookup 抑制二次 surprise |
| `MIMIR_WM_VOE_REPLAN_CTX` | `0` | `wm_learning_context` on surprise |
| `MIMIR_WM_VOE_CAPSULE` | `0` | （未实现）可选 HTML 镜像 |
| `MIMIR_WM_PREDICTOR` | `0` | 不变（Phase0 规则 MVP） |

### 单测

| 文件 | 覆盖 |
|------|------|
| [`tests/agent/test_wm_voe_learning_p11.py`](../../tests/agent/test_wm_voe_learning_p11.py) | record/lookup · replan_context · second_no_surprise |
| [`tests/agent/test_wm_voe_learning.py`](../../tests/agent/test_wm_voe_learning.py) | Phase0 JSONL + guard hook |

M6 已记：P11-01～04 · closeout 轮 tier0 **665 PASS**

---

## 与 Phase0 的差异

| 维度 | Phase0 (WB-B02) | Phase 1.1 |
|------|-----------------|-----------|
| **持久化** | JSONL only | JSONL + **`learned_surprises.json`** index |
| **Recall** | 无 | `lookup_learned_surprise` |
| **二次 surprise** | 每次仍触发 | `MIMIR_WM_VOE_RECALL=1` 时 **CLEAN** |
| **Replan 上下文** | warning only | 可选 `wm_learning_context` |
| **guard 流程** | detect → write | recall check → detect → write/context |

Phase0 [`world_model_spike.py`](../../agent/world_model_spike.py) **未改**；未接 turn 级 `prediction_expected_outcome` 到 event。

---

## 明确没做什么

| 类别 | 说明 |
|------|------|
| **Gateway / agent_loop 接线** | `wm_learning_context` 未自动进 prompt / replan LLM 调用 |
| **生产 env 默认开** | 所有 `MIMIR_WM_*` 在 repo/部署默认 **0** |
| **`persistent.json` mutator** | 未选 Path B；index 在 `data/wm_phase11/` |
| **HTML capsule 镜像** | `MIMIR_WM_VOE_CAPSULE` 未实现（scope 可选 staging） |
| **Fuzzy / embedding recall** | 仅精确 normalized pair |
| **LLM 世界模型预测器** | 仍规则 MVP |
| **Phase 1.2 分层规划** | plan §4 Multi-Scale — 另批 |
| **plan §3.2 / §3.3** | 信息密度探索 · 表面/语义加固 |
| **`voe_detector.py`** | 文件改动惊讶度 — 分轨 |
| **Wave A / A06.1** | search-first 工具守卫 — 独立 PR |
| **Horizon C / SESSION_SEARCH 默认** | 未触 |
| **Rubric 5.5** | 不宣称 IQ 过线 |

---

## 与 Wave A 边界

[`wave-a-closeout.md`](./wave-a-closeout.md) **不变**：rubric **4.9 + exception** · Q2 search-first **部分**。Phase 1.1 实现 VoE 学习闭环 **不**替代跨会话检索行为债。

---

## Staging 验收入口（可选）

```bash
export MIMIR_AETHER_HOME=~/.mimiraether
export MIMIR_WM_VOE_LEARNING=1
export MIMIR_WM_VOE_RECALL=1
export MIMIR_WM_VOE_REPLAN_CTX=1

cd ~/src/MimirAether
python3 - <<'PY'
from agent.degeneration_guard import DegenerationGuard
pair = ("operation success", "operation failed")
g = DegenerationGuard()
r1 = g.run_checks(expected_vs_actual=pair)
r2 = g.run_checks(expected_vs_actual=pair)
print("1st:", r1.signal.value, "| ctx:", r1.details.get("wm_learning_context", "")[:60])
print("2nd:", r2.signal.value, "| suppressed:", r2.details.get("surprise_suppressed"))
PY

wc -l "$MIMIR_AETHER_HOME/data/wm_phase0/surprise_events.jsonl"
cat "$MIMIR_AETHER_HOME/data/wm_phase11/learned_surprises.json" | python3 -m json.tool | head -20
```

**期望**：1st `surprise_detected` + 非空 `wm_learning_context`（若 REPLAN_CTX=1）· 2nd `clean` + `surprise_suppressed` · JSONL **1 行**。

关闭：`unset MIMIR_WM_VOE_LEARNING MIMIR_WM_VOE_RECALL MIMIR_WM_VOE_REPLAN_CTX` 或设为 `0`。

---

## 验证（本窗复跑）

```text
./run_ralph_tier0.sh  →  665 passed · Gate3 2 passed · Ralph Tier-0/1: PASS
```

---

## 后续（另批 · 非本 closeout）

| 项 | 说明 |
|----|------|
| **Phase 1.2** | 分层规划合约 · plan §4 |
| **Gateway 消费 `wm_learning_context`** | 需单独粒 + 重启策略 |
| **Capsule 镜像 / LLM predictor** | scope 可选 · Phase 2+ |
| **Wave A A06.1** | 跨会话 tool guard |

**WM Phase 1.1：结案。**
