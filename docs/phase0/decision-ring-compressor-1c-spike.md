# GATE-D1 · DecisionRing + Compressor 1c Spike

> **1c/1b/AUTO_EVOLVE 分界真源（GATE-D2）：** [`iqevo-1c-boundary.md`](./iqevo-1c-boundary.md) — D3 contract 引用条文 **B-***。

| 字段 | 值 |
|------|-----|
| **Date** | 2026-05-27 |
| **真源** | [`p2-long-iqevo-wave7-gate-cd-plan.md`](./p2-long-iqevo-wave7-gate-cd-plan.md) §7 · [`MIMIR_UNIFIED_PLAN.md`](../MIMIR_UNIFIED_PLAN.md) 冲突3 子阶段 **1c** |
| **状态** | Spike only — **无实现代码**；§46 签字前禁止 1c 工程 |
| **前置** | Gate C [x] · [`iqevo-gate-c-closeout.md`](./iqevo-gate-c-closeout.md) |

---

## 1. 范围与分工（1c vs 1b vs AUTO_EVOLVE）

| 轨道 | 职责 | 持久化 | 禁止 |
|------|------|--------|------|
| **1b AutoTuner** | Top-3 有界键：`compressor.threshold_percent`、`degeneration.loop_detection.threshold`、`tool_quality.degraded_threshold` | `$MIMIR_AETHER_HOME/data/tuned_thresholds.json` | 扩面到 DecisionRing 规则权重 |
| **1c（本 Spike）** | DecisionRing 策略面 + Compressor **第二档**旋钮（见 [`iqevo-1c-boundary.md`](./iqevo-1c-boundary.md) B-2、B-4） | 拟新增 `$MIMIR_AETHER_HOME/data/decision_compressor_policy.json`（名称待定，D3 定契约） | 写/改 **SKILL.md** |
| **AUTO_EVOLVE** | post-close analysis → `apply_evolution_from_analysis` | `skills/**/SKILL.md` | 改阈值 JSON、改 `degeneration_guard.json` 源 |

---

## 2. DecisionRing 可学参数面

**现状：** `DecisionRingConfig` + `StrategyMatcher` 规则表（`agent/decision_ring.py`、`agent/strategy_matcher.py`）；`recovery_mixin` / `core_loop` 消费 `DecisionResult`（`should_compress`、`backoff_seconds`、`suggested_actions`）。

| # | 参数（拟 1c 键） | 现默认值 | 建议范围 | 步长/类型 | 信号来源 |
|---|------------------|----------|----------|-----------|----------|
| D1 | `ring.max_retries` | 3 | 2–5 | 1 · int | `feedback_events` 中 `pipeline_close` + `error` 计数；`tune_audit` 相邻 session 失败率 |
| D2 | `ring.default_backoff_base` | 1.0 | 0.5–2.0 | 0.25 · float | 429/rate-limit 类 `feedback`；`DecisionResult.backoff_seconds` 滚动均值 |
| D3 | `ring.max_backoff` | 60.0 | 30–120 | 5 · float | 同上 + 长会话 tail latency |
| D4 | `ring.compress_context_pressure` | 0.85（隐含） | 0.70–0.95 | 0.05 · float | `context_pressure` 分布；`analysis_artifacts` 中 `tool_issues` / context 相关摘要 |
| D5 | `ring.truncate_context_pressure` | 0.95（隐含） | 0.85–1.0 | 0.05 · float | 同上；与 D4 保持 `truncate > compress` 不变量 |
| D6 | `rule.priority_bias.<rule_name>` | 0（每规则） | −2–+2 | 1 · int | `feedback` 按 `error_class` 聚合；`tune_audit` 某规则触发后仍失败则降权 |
| D7 | `rule.cooldown_scale` | 1.0 | 0.5–2.0 | 0.1 · float | 重复 `COMPRESS`/`TRUNCATE` 动作计数（`recovery_mixin` 日志摘要，只读） |
| D8 | `ring.confidence_floor` | 0.5 | 0.3–0.8 | 0.05 · float | analysis `overall_rating` + `confidence` 字段（artifact 摘要） |

**学习节奏（拟）：** 每次 `pipeline_close` 后 **至多 1 个** DecisionRing 键 nudge（与 1b「每 close 每键至多 1 次」对齐）；无信号则 no-op。

**DecisionRing 参数面条目数：8**

---

## 3. Compressor 可学参数面与 1b Top-3 边界

**分界全文：** [`iqevo-1c-boundary.md`](./iqevo-1c-boundary.md)（B-1～B-5）。Top-3 三键仅 1b；下列 C1–C6 为 1c 第二档。

### 3.1 Compressor 第二档（1c 拟管）

| # | 参数（拟 1c 键） | 现默认 | 建议范围 | 步长 | 信号来源 |
|---|------------------|--------|----------|------|----------|
| C1 | `compressor.protect_first_n` | 3 | 2–5 | 1 · int | 压缩后用户纠错率（`feedback`）；artifact 中「丢系统指令」类 tool_issues |
| C2 | `compressor.protect_last_n` | 6 | 4–10 | 1 · int | 同上；尾窗 tool 失败 |
| C3 | `compressor.summary_target_ratio` | 0.20 | 0.10–0.30 | 0.05 · float | 压缩次数 vs 会话长度（`feedback` `pipeline_close`）；EV-P05 重叠审计指标（只读） |
| C4 | `compressor.summary_failure_cooldown_s` | 600 | 300–900 | 60 · int | 摘要失败事件（`feedback` / 日志计数器，非 LLM 全文） |
| C5 | `compressor.preflight_relax_ratio` | 0.80 | 0.70–0.90 | 0.05 · float | preflight 误触发压缩率 |
| C6 | `compressor.tail_token_budget` | 4000（core_loop 注入） | 2000–8000 | 500 · int | 压缩后 token 峰值；与 **1b 的 threshold_percent 正交**（先 percent 触发，再 budget 塑形） |

**应用点：** `core_loop` 在构造 `MimirContextCompressor` 时合并：`get_tuned_float("compressor.threshold_percent")`（1b）+ `decision_compressor_policy.json` 第二档（1c）。**禁止** 1c `set_override` Top-3（boundary **B-2 / F5**）。

**Compressor 参数面条目数：6**

---

## 4. 数据输入与只读消费路径

```text
Wave 4 (只记录)
  $MIMIR_AETHER_HOME/data/feedback_events.jsonl
    ← feedback_collector.record_* (MIMIR_FEEDBACK_COLLECTOR=1)
    事件类型: tool_outcome, pipeline_close, analysis_artifact

Wave 5 (有界调参 · 1b)
  $MIMIR_AETHER_HOME/data/tuned_thresholds.json   # 1c 只读 Top-3 当前值
  $MIMIR_AETHER_HOME/data/tune_audit.jsonl         # 1c 只读审计，不追加 Top-3 写入

Post-close（只读摘要）
  $MIMIR_AETHER_HOME/data/analysis_artifacts/*.json
    字段: summary, overall_rating, tool_issues[], suggestions[].{target,action,priority}
    禁止: 将 suggested_changes 原文写回 SKILL（属 AUTO_EVOLVE）

拟 1c 输出（实现期）
  $MIMIR_AETHER_HOME/data/decision_compressor_policy.json
  $MIMIR_AETHER_HOME/data/decision_compressor_audit.jsonl
```

**聚合：** `experience_buffer.summarize_recent_experience()` 读 `feedback_events.jsonl` tail（已有，1b 复用）；1c learner **新增** `summarize_for_decision_compressor()` 时仍 **只读** 上述路径。

**不写 SKILL：** 1c 任何路径不得调用 `SkillEvolutionPipeline` / `write_skill_md_guarded`。

---

## 5. 风险与回滚

| 风险 | 缓解 |
|------|------|
| 1c 与 1b 同调 `threshold_percent` | 契约：Top-3 键仅 `auto_tuner.set_override`；1c policy 文件 schema 拒绝 Top-3 键 |
| 与 AUTO_EVOLVE 双写 skills | 分工表 §1；code review + `test_horizon_iqevo_wave7_1c.py`（D3） |
| DecisionRing 规则权重漂移 | 每键有界 + 每 close 至多 1 nudge + `decision_compressor_audit.jsonl` |
| 压缩过激损 recall | C3/C6 与 1b percent 分轨；回滚只清 policy 文件 |
| 无界改 `degeneration_guard.json` | **禁止**；guard 仅 1b 的 `loop_detection.threshold` 键 |

**回滚步骤：**

1. `rm -f $MIMIR_AETHER_HOME/data/decision_compressor_policy.json`（及 audit 若需）
2. 保留 `tuned_thresholds.json`（1b）或 `reset_overrides_for_tests()` 仅测试环境
3. `MIMIR_AUTO_EVOLVE=0` **不** 替代 1c 回滚（EVOLVE 管 SKILL）；关 EVOLVE 见 [`iqevo-gate-c-closeout.md`](./iqevo-gate-c-closeout.md)
4. `restart_gateway_hard.sh` + tier0 1×

---

## 6. 模块 touch 表

| 模块 | 改动类型 | 1c 拟改动（实现期） |
|------|----------|---------------------|
| `agent/decision_ring.py` | **读** policy；**写** audit | 加载 D1–D8；`decide()` 使用有界 backoff/pressure；不修改 `strategy_matcher` 源码规则表，只调 `priority_bias` |
| `agent/context_compressor.py` | **读** policy；**配置** 构造参数 | `ContextCompressorV2.__init__` 接受第二档；`should_compress` / `compress` 行为不变，参数来自 policy |
| `agent/recovery_mixin.py` | **读** | 消费 `DecisionResult`（已有）；可选记录 action 统计供 1c 聚合（只写 audit，不写 SKILL） |
| `agent/core_loop.py` | **读**；**配置** compressor 构造 | 合并 `get_tuned_float`（1b）+ policy loader（1c）；`decision_ring` 构造后注入 policy |

**说明：** 仓库中 compressor 为单文件 `agent/context_compressor.py`（非目录）；与 plan 中 `agent/context_compressor/` 等价指该模块。

**模块 touch 表行数：4**

---

## 7. 验收（D3 / §47 前）

- [ ] Contract 草案：[`iqevo-1c-contract-draft.md`](./iqevo-1c-contract-draft.md)（**1C-01～1C-07**）→ §49 实现
- [ ] 契约条文：[`iqevo-1c-boundary.md`](./iqevo-1c-boundary.md) **B-1～B-5** → ≥5 条 pytest
- [ ] `decision_compressor_policy.json` JSON Schema v1 + 越界拒绝（含 Top-3 拒绝，**F5**）
- [ ] tier0 3× 连绿（1c 实现粒，非本 Spike）
- [ ] `docs/evolution_log.md` 一行（触达 agent/）

---

## 8. 非目标（Spike）

- Unified Plan 1c **代码**实现（§47–§49）
- 扩 `tuned_thresholds._REGISTRY` Top-3 键面
- IntentPredictor / 全量语义记忆（§51 可选）
- Gate D4 刘哥签字（§46）
