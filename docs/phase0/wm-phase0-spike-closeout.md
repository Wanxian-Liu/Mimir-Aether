# WM Phase0 spike closeout（WB-B03）

> **日期**：2026-06-01  
> **拍板**：§20.3 **WM-HORIZON-01** ✅  
> **真源**：[`wm-phase0-spike-scope.md`](./wm-phase0-spike-scope.md) · [`wave-b-execution-plan.md`](./wave-b-execution-plan.md)  
> **前置**：Wave A closeout — rubric **4.9 + exception**（[`wave-a-closeout.md`](./wave-a-closeout.md)）· **非** 5.5 过线

---

## 完成了什么

| 粒 | 交付 | 证据 |
|:--:|------|------|
| **WB-B00** | Spike 范围 + 代码地图 | [`wm-phase0-spike-scope.md`](./wm-phase0-spike-scope.md) |
| **WB-B01** | 规则/heuristic 世界模型预测器 | [`agent/world_model_spike.py`](../../agent/world_model_spike.py) · `Prediction` + `predict(context_snapshot)` · `MIMIR_WM_PREDICTOR` 默认 **0** |
| **WB-B02** | VoE surprise → JSONL 学习事件 | [`agent/wm_voe_learning.py`](../../agent/wm_voe_learning.py) · [`degeneration_guard.py`](../../agent/degeneration_guard.py) `run_checks` hook · `MIMIR_WM_VOE_LEARNING` 默认 **0** |
| **WB-B03** | 本文档 + tier0 复验 | `./run_ralph_tier0.sh` **659 PASS**（Gate3 2 PASS） |

### B01 预测器（摘要）

- 输入：`context_snapshot` dict（可含 `user_message` / `intent` / `objective`）
- 输出：`Prediction(next_context_needs, applicable_skills, expected_outcome)`
- 纯规则：无 LLM API、无网络、无随机
- 单测：[`tests/agent/test_world_model_spike.py`](../../tests/agent/test_world_model_spike.py)（6 tests）

### B02 JSONL 路径与 schema（摘要）

- **路径**：`$MIMIR_AETHER_HOME/data/wm_phase0/surprise_events.jsonl`（目录自动创建）
- **触发**：`DegenerationGuard.run_checks(expected_vs_actual=…)` → `detect_surprise` 命中且 `MIMIR_WM_VOE_LEARNING=1`
- **schema**（`schema_version=1`，`event_type=voe_surprise`）：

```json
{
  "schema_version": 1,
  "event_type": "voe_surprise",
  "timestamp": 1735689600.0,
  "expected": "command success",
  "actual": "command failed",
  "surprise_label": "outcome reversal",
  "context_snapshot": {},
  "guard_message": "🔴 SURPRISE_DETECTED: outcome reversal — ..."
}
```

- 写入失败：仅 `logger.warning`，不阻塞 replan
- 单测：[`tests/agent/test_wm_voe_learning.py`](../../tests/agent/test_wm_voe_learning.py)（5 tests）

### 验证（本窗复跑）

```text
./run_ralph_tier0.sh  →  659 passed · Gate3 2 passed · Ralph Tier-0/1: PASS
```

M6 已记（B01/B02）：`world_model_spike rule MVP` · `VoE surprise→JSONL + guard hook`

---

## 明确没做什么

| 类别 | 说明 |
|------|------|
| **Gateway / agent loop 接线** | 未在 `prompt_builder` / `agent_loop` / gateway 默认注入 predictor 或学习路径 |
| **生产 env 默认开** | `MIMIR_WM_PREDICTOR=0` · `MIMIR_WM_VOE_LEARNING=0` — 生产行为与 spike 前一致 |
| **Phase 1.2 分层规划全量** | 无 Multi-Scale 规划器、无合约反馈链 |
| **`voe_detector.py`** | 自进化**文件改动**惊讶度未接本 spike；仍仅 `exec_mixin` log |
| **第二次 surprise 消除** | 无 memory recall 覆盖同场景；JSONL 为 audit trail only |
| **SESSION_SEARCH 默认** | 未改 `SESSION_SEARCH_BACKEND` / hybrid 生产默认 |
| **Rubric 5.5 / Wave A 过线** | 不宣称 IQ 战役达标 |

---

## 与 Wave A 的边界

Wave A 出口（[`wave-a-closeout.md`](./wave-a-closeout.md)）**不变**：

| 维度 | 状态 |
|------|------|
| **Q1 rubric** | **4.9 + exception**（未达 5.5） |
| **Q2 检索** | **部分** — 生产 search-first 未过（A09 FAIL×2；filtered 义务句 100% 违例） |
| **WM 角色** | 证明「预测 + 意外→可审计学习事件」**可测**；**不**替代「历史类必先 session_search」行为债 |

**A06.1**（跨会话句工具守卫）仍为 **独立 PR**，不并入 Wave B 或 Phase 1.1 默认范围。

---

## 与 Phase 1.1 的差距（plan §3.1）

Phase0 完成了 plan §3.1 的 **第一步**（意外不再仅丢弃：有 JSONL 记录）。Phase **1.1** 仍缺：

| 1.1 目标 | Phase0 现状 | 差距 |
|----------|-------------|------|
| **surprise → memory capsule** | JSONL under `data/wm_phase0/` | 未写 `memory_write_facade` / HTML capsule / `persistent.json` mutator |
| **replan 带学习上下文** | replan 语义同前（warning + `needs_replan`） | 无 `extra_context="注意：之前的预期…已记录学习"` |
| **LLM 世界模型预测器** | 规则 `world_model_spike.predict` | 无 LLM API；`prediction_expected_outcome` 未接 turn 级 hook |
| **验证：同场景不再二次 surprise** | 未实现 | 需 memory recall + 预测校准（plan 验证标准） |

另：plan §3.2 信息密度→主动探索、§3.3 表面/语义意外加固 — **均未**在本 spike 范围。

**下一批**（刘哥另批）：Phase 1.1 生产化 Wave / 独立 PR；与 Horizon C、A06.1 继续分轨。

---

## 手动验 spike（可选）

在 **runtime home**（非 git）验证 JSONL 写入，不影响 tier0：

```bash
export MIMIR_AETHER_HOME=~/.mimiraether
export MIMIR_WM_VOE_LEARNING=1

cd ~/src/MimirAether
python3 - <<'PY'
from agent.degeneration_guard import DegenerationGuard

g = DegenerationGuard()
r = g.run_checks(expected_vs_actual=("operation success", "operation failed"))
print("signal:", r.signal.value)
print("warnings:", r.warnings)
PY

# 期望：signal=surprise_detected；JSONL 新增一行
tail -1 "$MIMIR_AETHER_HOME/data/wm_phase0/surprise_events.jsonl" | python3 -m json.tool
```

**注意**：`("success","failed")` 单独用词可能不命中关键词对立；应用 **success / fail** 子串对，如 `("operation success", "operation failed")`（与单测一致）。

关闭学习（恢复生产默认行为）：

```bash
unset MIMIR_WM_VOE_LEARNING   # 或 export MIMIR_WM_VOE_LEARNING=0
```

---

## 证据索引

| 文档 / 代码 | 用途 |
|-------------|------|
| [`wm-phase0-spike-scope.md`](./wm-phase0-spike-scope.md) | Spike in/out · 验收 |
| [`wave-b-execution-plan.md`](./wave-b-execution-plan.md) | WB-B00～B03 工程粒 |
| [`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md) §3.1 | Phase 1.1 路线图 |
| [`wave-a-closeout.md`](./wave-a-closeout.md) | IQ 4.9 · Q2 部分 · A06.1 独立 |

**Wave B Phase0 spike：结案。**
