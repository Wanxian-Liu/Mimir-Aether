# WM Phase 1.1 scope（WM-P11-00）

> **拍板**：刘哥 **另批** Phase 1.1（post Wave B closeout）  
> **前置**：[`wm-phase0-spike-closeout.md`](./wm-phase0-spike-closeout.md) · plan [`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md) §3.1  
> **执行表**：[`wm-phase11-execution-plan.md`](./wm-phase11-execution-plan.md) WM-P11-00～04  
> **真源代码**：[`agent/wm_voe_learning.py`](../../agent/wm_voe_learning.py) · [`agent/memory_write_facade.py`](../../agent/memory_write_facade.py) · [`agent/degeneration_guard.py`](../../agent/degeneration_guard.py)

---

## Spike 一句话（Phase 1.1）

在 Phase0「JSONL 审计 + 告警/replan」之上，补齐 plan §3.1 **学习模式**：surprise 写入 **可 recall 的结构化学习库**，replan 路径携带 **学习上下文**，并对 **同一 (expected, actual) 第二次检测不再触发 surprise**（单测可证）；**仍** env 门控、**不** gateway 默认全开。

---

## In scope（WM-P11-01～03）

| # | ID | 条目 | 路径意向 | 可验证标准 |
|---|-----|------|----------|------------|
| 1 | **P11-01** | surprise → **可 recall 学习库** | 扩展 `agent/wm_voe_learning.py` · `$MIMIR_AETHER_HOME/data/wm_phase11/learned_surprises.json` | 首次 surprise 写入 index；`lookup_learned_surprise(expected, actual)` 命中 |
| 2 | **P11-01b** | 保留 Phase0 JSONL 审计 | 现有 `data/wm_phase0/surprise_events.jsonl` | env=1 时 **仍 append**（audit 与 index 双写） |
| 3 | **P11-01c** | 可选 HTML 胶囊镜像 | `memory_write_facade.write_capsule_html` · `$MIMIR_AETHER_HOME/memory/capsules/wm-voe-{id}.html` | **staging 可选** · `MIMIR_WM_VOE_CAPSULE=1`；非 P11-03 硬依赖 |
| 4 | **P11-02** | replan **学习上下文** | `DegenerationReport.details["wm_learning_context"]` 或等价字段 · `run_checks` 返回 | 首次 surprise 非空中文/英文提示块；消费方（replan 调用者）可读 **不强制** gateway 接线 |
| 5 | **P11-03** | **第二次不 surprise** | `degeneration_guard.run_checks` 在 `detect_surprise` **前** consult lookup | 同 tuple 第二次 → `signal=CLEAN`（或 `surprise_suppressed=true` in details） |
| 6 | **P11-03b** | 单测 / contract | `tests/agent/test_wm_voe_learning_p11.py`（或扩展现有文件） | 见下文验收 |

**Env（Phase 1.1 · 默认全关）**

| 变量 | 默认 | 含义 |
|------|------|------|
| `MIMIR_WM_VOE_LEARNING` | `0` | Phase0 行为：JSONL +（1.1）index 双写 |
| `MIMIR_WM_VOE_RECALL` | `0` | 启用 lookup → 抑制二次 surprise |
| `MIMIR_WM_VOE_REPLAN_CTX` | `0` | 在 report 中填充 `wm_learning_context` |
| `MIMIR_WM_VOE_CAPSULE` | `0` | 可选 HTML 胶囊镜像（staging） |
| `MIMIR_WM_PREDICTOR` | `0` | 不变；1.1 **不**要求 LLM 预测器 |

---

## Out of scope

| 类别 | 说明 |
|------|------|
| **Phase 1.2 分层规划全量** | Multi-Scale 规划器 · 合约反馈链 · plan §4 |
| **Gateway / agent_loop 默认接线** | 不在 `prompt_builder` 默认注入；不将 replan context 自动进 LLM system prompt |
| **生产 env 默认全开** | 任何 `MIMIR_WM_*` 在 repo/镜像中保持 **0**；仅 staging `.env` 或人工 export |
| **Wave A / A06.1** | search-first 工具守卫 · SESSION_SEARCH 默认 · rubric 5.5 |
| **Horizon C / OPS 日常粒** | P3-XSR · ENGINE · 飞书 L2 等 |
| **`voe_detector.py`** | 自进化**文件改动**惊讶度 — 与 turn 级 `surprise_gate` 分轨 |
| **LLM 世界模型预测器** | Phase 1.1+ / 2.x；规则 `world_model_spike` 可填 `context_snapshot` 但不调 API |
| **plan §3.2 / §3.3** | 信息密度→探索 · 表面/语义加固 |
| **`persistent.json` mutator（Path B）** | 见下节 — **本 Phase 明确不选** |
| **第二次消除的语义泛化** | 仅 **精确** `(expected, actual)` 归一化匹配；模糊/embedding 匹配属 Phase 2+ |

---

## Memory 路径选型

### 决策摘要

| 路径 | Phase 1.1 | 角色 |
|------|:-----------:|------|
| **A · HTML capsule** | 可选镜像 | 人/agent 经 `list_capsules` 浏览；**非** P11-03 主 recall |
| **B · `persistent.json` mutator** | **不选** | — |
| **C · `data/wm_phase11/` 结构化 index** | **主 recall** | 机器 lookup · 单测 · 低耦合 |

### 不选 Path B（persistent mutator）的理由

1. **ADR-002 / ADR-001**：Path B 面向低 churn 的 `skill_usage` / `progress`；surprise 为 **高频 episodic**，易膨胀 `persistent.json` 并增加 single-writer 争用与回归面。  
2. **Phase0 先例**：spike 已明确 learning 事件 **不进** git / persistent（见 [`wm-phase0-spike-scope.md`](./wm-phase0-spike-scope.md)）。  
3. **Recall 形状**：P11-03 需 `(expected, actual)` **精确键** lookup；JSON index 比 mutator merge 更简单、可测。  
4. **隔离**：runtime `data/wm_phase11/` 与 capsule 真源分离，失败不 corrupt 核心 persistent。

### 选用 Path C + 可选 Path A

**主路径（P11-01 / P11-03）**：`$MIMIR_AETHER_HOME/data/wm_phase11/learned_surprises.json`

```json
{
  "schema_version": 1,
  "entries": {
    "operation success|operation failed": {
      "expected": "operation success",
      "actual": "operation failed",
      "surprise_label": "outcome reversal",
      "first_seen": 1735689600.0,
      "last_seen": 1735689600.0,
      "hit_count": 1,
      "learning_hint": "Prior VoE: expected success but got failure; do not repeat same assumption."
    }
  }
}
```

- **键**：`normalize(expected)|normalize(actual)`（strip + lower；与 `detect_surprise` 输入一致）  
- **写入**：`record_surprise_learning(...)` 在 `append_surprise_event` 内或紧后调用（env 门控）  
- **读取**：`lookup_learned_surprise(expected, actual) -> dict | None`

**可选 Path A（staging）**：当 `MIMIR_WM_VOE_CAPSULE=1` 时，用 `write_capsule_html` 写 `memory/capsules/wm-voe-{unix_ts}.html`，frontmatter 含 `tags: [voe-surprise, wm-phase11]`，便于 `list_capsules(tag_filter=...)` — **不**替代 index lookup。

**Phase0 JSONL**：继续 append-only audit；与 index **双写**（同 env `MIMIR_WM_VOE_LEARNING=1`）。

---

## WM-P11-01～03 验收

### WM-P11-01 · surprise → recall 库

**命令**

```bash
cd ~/src/MimirAether
python3 -m pytest -q tests/agent/test_wm_voe_learning_p11.py -k "record_or_lookup"
./run_ralph_tier0.sh
```

**断言类型**

| 测试 | 断言 |
|------|------|
| 首次 record | tmp_path index 含 1 entry；键为 normalized pair |
| JSONL 双写 | 同触发 JSONL 仍 +1 行（mock path） |
| lookup hit | 写入后 `lookup_learned_surprise(exp, act)` 非 None |
| env=0 | 无 index / JSONL 写入 |

---

### WM-P11-02 · replan 学习上下文

**命令**

```bash
python3 -m pytest -q tests/agent/test_wm_voe_learning_p11.py -k "replan_context"
```

**断言类型**

| 测试 | 断言 |
|------|------|
| 首次 surprise + `MIMIR_WM_VOE_REPLAN_CTX=1` | `report.details["wm_learning_context"]` 含 expected/actual 摘要 |
| env=0 | 字段 absent 或空；原有 `warnings` / `needs_replan` 不变 |
| 文案 | 对齐 plan §3.1 意图（已记录学习 / prior VoE）— 不要求 gateway 消费 |

**非验收**：飞书/ gateway 日志出现该字符串。

---

### WM-P11-03 · 「第二次不 surprise」操作定义

**定义（plan §3.1 验证标准在本 repo 的可操作版）**

给定归一化后的 `(expected, actual)` 对（与单测一致，推荐 `("operation success", "operation failed")`）：

| 步骤 | 操作 | 期望 |
|:----:|------|------|
| 1 | `MIMIR_WM_VOE_LEARNING=1` · `MIMIR_WM_VOE_RECALL=1` · 第一次 `run_checks(expected_vs_actual=pair)` | `signal == SURPRISE_DETECTED` · index 有 entry · JSONL +1 |
| 2 | **不修改** index · 第二次 `run_checks(expected_vs_actual=pair)` | `signal == CLEAN` **且** `detect_surprise` 逻辑被跳过或等价抑制 |
| 3 | `details` | 可选 `surprise_suppressed=true` · `suppressed_reason=learned_voe` |

**「不 surprise」=** 第二次 **不** 产生 `DegenerationSignal.SURPRISE_DETECTED`、**不** 追加 JSONL 行（或 append 带 `event_type=voe_suppressed` — 实现时二选一并在单测固定；**推荐** 完全不 append 以避免 audit 噪声）。

**命令**

```bash
python3 -m pytest -q tests/agent/test_wm_voe_learning_p11.py -k "second_no_surprise"
```

**非验收**：语义相似但字符串不同的 pair 不抑制（无 fuzzy match）。

---

## Staging 门控（生产默认仍 0）

| 环境 | 配置位置 | 建议值 | 说明 |
|------|----------|--------|------|
| **生产 / 默认** | （unset） | 全部 `0` | 与 Phase0 行为一致：仅 surprise warn/replan |
| **Staging 手动** | shell export 或 `$MIMIR_AETHER_HOME/.env` | 见下 | **不** commit `.env` · **不**改 gateway systemd 默认 |
| **CI / tier0** | 单测 `monkeypatch` | 按测设 | 不依赖 staging home |

**Staging 全开示例（仅人工验收入口）**

```bash
export MIMIR_AETHER_HOME=~/.mimiraether
export MIMIR_WM_VOE_LEARNING=1
export MIMIR_WM_VOE_RECALL=1
export MIMIR_WM_VOE_REPLAN_CTX=1
# 可选：
# export MIMIR_WM_VOE_CAPSULE=1

cd ~/src/MimirAether
python3 - <<'PY'
from agent.degeneration_guard import DegenerationGuard
pair = ("operation success", "operation failed")
g = DegenerationGuard()
r1 = g.run_checks(expected_vs_actual=pair)
r2 = g.run_checks(expected_vs_actual=pair)
print("first:", r1.signal.value, "ctx:", r1.details.get("wm_learning_context", "")[:80])
print("second:", r2.signal.value, r2.details)
PY

ls -la "$MIMIR_AETHER_HOME/data/wm_phase11/"
tail -1 "$MIMIR_AETHER_HOME/data/wm_phase0/surprise_events.jsonl"
```

**关闭**：`unset MIMIR_WM_VOE_LEARNING MIMIR_WM_VOE_RECALL MIMIR_WM_VOE_REPLAN_CTX MIMIR_WM_VOE_CAPSULE` 或设为 `0`。

**Gateway**：staging 验收入口 **不要求** 重启 gateway；若将来在 agent loop 消费 `wm_learning_context`，另开 WM-P11-05+ 粒并单独 closeout。

---

## 与 Wave A / Phase0 边界

| 维度 | 状态 |
|------|------|
| Wave A rubric | **4.9 + exception** 不变 — 见 [`wave-a-closeout.md`](./wave-a-closeout.md) |
| Q2 search-first | **部分** — Phase 1.1 **不**替 A06.1 |
| Phase0 JSONL | 保留；1.1 为 **增量** 非替换 |
| tier0 基线 | 合入 P11 后须 `./run_ralph_tier0.sh` 绿 |

---

## 风险

| 风险 | 缓解 |
|------|------|
| index 与 JSONL 不一致 | 单测双写；失败 log warning |
| 精确 match 过窄 | 文档标明 Phase 2 fuzzy；P11-03 只测 exact pair |
| 误开 production env | 默认 0 + closeout 声明；无 systemd 改动 |
| scope creep → 1.2 / gateway | 本 scope Out 表 + 独立 PR |

---

## 下游粒预览

| ID | 依赖本 scope |
|----|----------------|
| **WM-P11-01** | §Memory Path C · §P11-01 验收 |
| **WM-P11-02** | §P11-02 · `wm_learning_context` |
| **WM-P11-03** | §第二次不 surprise 定义 · §P11-03 验收 |
| **WM-P11-04** | tier0 + `wm-phase11-closeout.md` |

**下一窗**：**WM-P11-01** — 实现 `learned_surprises.json` + lookup/record（在 `wm_voe_learning.py` 扩展）。
