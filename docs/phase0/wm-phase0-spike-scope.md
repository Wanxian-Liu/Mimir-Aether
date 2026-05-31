# WM Phase0 spike scope（WB-B00）

> **拍板**：§20.3 **WM-HORIZON-01** ✅（2026-05-31）  
> **前置**：Wave A closeout — rubric **4.9 + exception**（[`wave-a-closeout.md`](./wave-a-closeout.md)）· **非** 5.5 过线  
> **真源**：[`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md) §1–§3.1 · [`world-model-agent-handoff.md`](../superpowers/plans/2026-05-27-world-model-agent-handoff.md) §7  
> **执行表**：[`wave-b-execution-plan.md`](./wave-b-execution-plan.md) WB-B00～B03

---

## Spike 一句话

**Phase0 竖切** = 在 Mimir 里用 **规则/heuristic 世界模型预测器**（不调 LLM API）从当前上下文快照产出 `Prediction(expected_outcome, …)`，并在 **`surprise_gate` 触发时**（预期 vs 实际语义矛盾）走 **VoE→学习事件** 的最小持久化路径（JSONL append），证明「告警 → 可回放学习记录」闭环可测；**不**接 gateway 默认、**不**做分层规划全量。

对齐 plan §2 架构图的两块：**世界模型预测器**（WB-B01）+ **VoE 检测 → SIGReg/学习器** 的最小桩（WB-B02，仅 surprise 事件落盘）。

---

## In scope（WB-B01 / WB-B02）

| # | 条目 | 路径意向 | 可验证标准 |
|---|------|----------|------------|
| 1 | **WorldModelPredictor 规则 MVP** | `agent/world_model_spike.py` · `tests/agent/test_world_model_spike.py` | 给定 `context_snapshot` dict → `Prediction` 含 `next_context_needs` / `applicable_skills` / `expected_outcome`；纯函数、无网络 |
| 2 | **VoE 学习事件写入** | `agent/wm_voe_learning.py`（或同模块内 writer）· `$MIMIR_AETHER_HOME/data/wm_phase0/surprise_events.jsonl` | `surprise_gate` 触发后 append 一行 JSON；字段见下文 WB-B02 schema |
| 3 | **最小 hook（非大重构）** | `agent/degeneration_guard.py` — `detect_surprise` 返回非 None 时调用 writer（**env 门控** `MIMIR_WM_VOE_LEARNING`，默认 **0**） | 单测 mock writer：`run_checks(expected_vs_actual=…)` → 断言 1 条 event；**不**改 gateway |

**Env（spike 期，默认全关）**

| 变量 | 默认 | 含义 |
|------|------|------|
| `MIMIR_WM_VOE_LEARNING` | `0` | 开启 surprise→JSONL 学习事件 |
| `MIMIR_WM_PREDICTOR` | `0` | 预留 B01 生产调用门（spike 仅单测直接 import） |

---

## Out of scope

| 类别 | 说明 |
|------|------|
| **Horizon C** | §19.1 工程粒已结案；不混 P3-XSR / ENGINE / OPS 日常 |
| **Wave A / A06.1** | search-first 工具守卫、飞书复测 — **独立 PR**，本 spike 不替 A 还债 |
| **Phase 1.2+** | 分层规划器全量（plan §4）、预测式检索生产化、SIGReg 探索策略 |
| **像素 / 仿真世界模型** | 非 Agent 表征空间目标 |
| **`SESSION_SEARCH_BACKEND` 生产默认** | 禁止改动 hybrid/semantic 默认 |
| **Gateway 默认接线** | 不在 agent loop / prompt_builder 默认注入 predictor；不重启 gateway 作为 B01/B02 验收条件 |
| **`data/persistent.json` commit** | 学习事件写 runtime home JSONL，不进 git |
| **Rubric 5.5** | Wave B 不宣称 IQ 战役过线 |
| **`degeneration_guard` 大重构** | 仅允许 detect_surprise 尾部 ≤10 行 hook |
| **LLM 调用预测器** | B01 仅规则 MVP；LLM 预测属 Phase 1.1+ |

---

## 代码地图（引用 only · 本窗不重构）

### `agent/degeneration_guard.py` — surprise_gate（告警 today）

| 符号 | 行为 |
|------|------|
| `DegenerationGuard.detect_surprise(expected, actual)` | 关键词对立（found/not found, success/fail）→ **warning 字符串** + `logger.warning`；**无** memory/JSONL |
| `DegenerationGuard.run_checks(expected_vs_actual=…)` | surprise → `DegenerationReport.warnings` + `needs_replan()`；仍 **无学习** |
| 配置 | `$MIMIR_AETHER_HOME/data/degeneration_guard.json`（或 repo `data/degeneration_guard.json`）§ `surprise_gate` |

**Gap（plan §3.1）**：意外被丢弃；WB-B02 在触发点 **追加** 学习事件，保留现有 replan/warn 语义。

### VoE 相关（勿与 B02 混为一谈）

| 模块 | 用途 | Phase0 |
|------|------|--------|
| `agent/self_evolution/voe_detector.py` | 自进化 **文件改动** 惊讶度（z-score） | **不接线**；`exec_mixin.py` 仅 log WARNING |
| `degeneration_guard.surprise_gate` | **turn 级 expected vs actual** | **B02 接线点** |

### Memory 写路径（学习事件 **不** 走 capsule 默认）

| 路径 | 模块 | Phase0 用法 |
|------|------|-------------|
| Path A capsules | `agent/memory_write_facade.py` → `write_capsule_html` | **Out** — spike 不写 HTML capsule |
| Path B persistent | `memory_write_facade.write_persistent_mutator` / `persistent_store` | **Out** — 不 mutator 进 persistent.json |
| **Spike JSONL** | 新建 `wm_voe_learning.append_surprise_event` | **In** — append-only audit trail |

### `agent/intent_predictor.py` — 预测输入（只读参考）

| 符号 | 行为 |
|------|------|
| `predict(user_message)` → `IntentPrediction` | 规则 MVP：`intent` / `complexity` / `prefer_session_search` |
| `build_intent_context_block` | 注入 `<intent-context>`（gateway 已接线，Wave A07 证据） |
| 门控 | `MIMIR_INTENT_PREDICTOR` 默认 `1` |

**关系**：B01 `context_snapshot` 可 **复用** intent 字段作 heuristic 输入；**不**改 intent_predictor 行为。

### 检索 / 跨会话（地基只引用）

| 模块 | 角色 |
|------|------|
| `tools/session_search_tool.py` | 跨会话检索 — Phase0 **不**改默认 backend |
| `agent/cross_session_retrieval.py` | L2 prefetch — 与世界模型 **并行轨**，非本 spike |

### 数据流（Phase0 目标态 · 桩）

```text
context_snapshot ──► world_model_spike.predict() ──► Prediction.expected_outcome
                                                          │
turn 结束 / tool 结果 ──► run_checks(expected, actual) ──► surprise_gate?
                                                          │
                                    MIMIR_WM_VOE_LEARNING=1 ──► surprise_events.jsonl
```

---

## WB-B01 验收

**命令**

```bash
cd ~/src/MimirAether
python3 -m pytest -q tests/agent/test_world_model_spike.py
./run_ralph_tier0.sh   # B03 全量；B01 合入后须绿
```

**断言类型（单测）**

| 测试 | 断言 |
|------|------|
| `Prediction` 结构 | dataclass 字段存在：`next_context_needs`（list/str）、`applicable_skills`（list）、`expected_outcome`（str） |
| 规则 predict | 给定 snapshot（含 `user_message` / `intent` / `objective` 键）→ 非空 `expected_outcome`；skills 列表为 str |
| 确定性 | 同 snapshot 两次调用结果一致（无随机、无 I/O） |
| 边界 | 空 snapshot → 不抛；返回保守默认 Prediction |

**非验收**：gateway 日志、飞书行为、LLM API 调用。

---

## WB-B02 验收

### 持久化 schema（`surprise_events.jsonl` · 一行一事件）

```json
{
  "schema_version": 1,
  "event_type": "voe_surprise",
  "timestamp": 1735689600.0,
  "expected": "command succeeded",
  "actual": "command failed",
  "surprise_label": "outcome reversal",
  "context_snapshot": {
    "session_id": "optional",
    "user_message_snippet": "optional",
    "prediction_expected_outcome": "optional-from-B01"
  },
  "guard_message": "🔴 SURPRISE_DETECTED: ..."
}
```

- **路径**：`$MIMIR_AETHER_HOME/data/wm_phase0/surprise_events.jsonl`（目录自动创建）
- **写入**：append-only；失败 **log warning**，不阻塞 replan
- **默认**：`MIMIR_WM_VOE_LEARNING=0` → writer no-op（单测显式 env=1 或 inject mock path）

### 单测（mock 即可）

**命令**

```bash
python3 -m pytest -q tests/agent/test_wm_voe_learning.py
```

**断言类型**

| 测试 | 断言 |
|------|------|
| `append_surprise_event` | tmp_path 下写 1 行；JSON 解析；必填字段齐全 |
| `detect_surprise` hook | mock writer：`run_checks(expected_vs_actual=("success","failed"))` → writer 调用 1 次；env=0 → 0 次 |
| 幂等/追加 | 两次触发 → 文件 2 行 |

**非验收**：第二次同场景不再 surprise（plan §3.1 长期标准 — **Phase 1.1**）；memory tool 自动 recall。

---

## 风险与 Wave A 边界

| 风险 | 缓解 |
|------|------|
| **WM 被误当作 search-first 修复** | Phase0 **不**改 `SESSION_SEARCH_GUIDANCE`、**不**加 session_search 工具守卫；Wave A Q2 **部分**（A09 FAIL×2、filtered 义务句 100%）留 **A06.1** 独立 PR |
| **surprise 与学习语义混淆** | `voe_detector`（改文件）与 `surprise_gate`（turn 结果）文档分列；B02 只接后者 |
| **persistent.json 污染** | 学习事件仅 JSONL under `data/wm_phase0/`；禁止 spike commit runtime persistent |
| **scope creep → 分层规划** | plan §4 Multi-Scale **Out**；B01 `next_context_needs` 仅为 list 占位，非规划器 |
| **gateway 行为漂移** | env 默认 off；closeout 必须写「生产未启用」 |

**与 Wave A 关系（一句话）**：世界模型 Phase0 证明 **「预测 + 意外→可审计学习事件」** 可测；**不**替代「历史类必先 session_search」行为债（见 [`wave-a-closeout.md`](./wave-a-closeout.md) §未达 5.5）。

---

## 下游粒预览

| ID | 依赖本 scope |
|----|----------------|
| **WB-B01** | §In scope #1 · §WB-B01 验收 |
| **WB-B02** | §In scope #2–#3 · §WB-B02 schema |
| **WB-B03** | tier0 + `wm-phase0-spike-closeout.md` + bridge §4 |

**下一窗**：**WB-B03** — `wm-phase0-spike-closeout.md` + tier0 确认 + plan 全表 [x]。
