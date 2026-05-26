# IQ-EVO · 1c 与 1b / AUTO_EVOLVE 分界（GATE-D2 真源）

| 字段 | 值 |
|------|-----|
| **Date** | 2026-05-27 |
| **Grain** | GATE-D2 / handoff §44 |
| **引用** | [`decision-ring-compressor-1c-spike.md`](./decision-ring-compressor-1c-spike.md)（参数面 D1–D8、C1–C6）· [`p2-long-iqevo-wave7-gate-cd-plan.md`](./p2-long-iqevo-wave7-gate-cd-plan.md) §7 |
| **D3 contract** | 本节条文编号 **B-*** 可直接映射 `test_horizon_iqevo_wave7_1c.py` 断言 |

---

## B-1 · 1c 不写 / 不改 SKILL.md

1. **禁止** 1c 代码路径调用 `SkillEvolutionPipeline`、`write_skill_md_guarded`、`create_skill_dir_guarded` 或等价「落盘 SKILL」API。
2. **禁止** 将 `analysis_artifacts` 内 `suggestions[].suggested_changes` 写入 `skills/**/SKILL.md`（该职责仅 **E-009 / `MIMIR_AUTO_EVOLVE`**）。
3. **允许** 1c 只读 artifact 的 `summary`、`overall_rating`、`tool_issues`、`suggestions[].{target,action,priority,confidence}` 作调参信号。
4. **允许** 1c 输出仅：`decision_compressor_policy.json` + `decision_compressor_audit.jsonl`（路径名实现期可定，schema 由 GATE-D3 锁定）。

---

## B-2 · 1c 不替代 Top-3 `tuned_thresholds` 键

**Top-3 全名（仅 1b `AutoTuner` + `set_override` 可写）：**

| 键名 | Registry 默认 | 有界范围 | 1b 消费方 |
|------|---------------|----------|-----------|
| `compressor.threshold_percent` | 0.50 | 0.35–0.70 | `core_loop` → `MimirContextCompressor` |
| `degeneration.loop_detection.threshold` | 3 | 2–5 | `degeneration_guard` |
| `tool_quality.degraded_threshold` | 0.50 | 0.30–0.70 | `tool_quality` / prompt 注入 |

**1c 硬约束：**

- 不得向 `$MIMIR_AETHER_HOME/data/tuned_thresholds.json` 写入上述三键（含别名、前缀欺骗）。
- 不得扩 `agent/tuned_thresholds.py` 的 `_REGISTRY` 新增「第四 Top 键」冒充 1c（扩 registry 属 **禁止项 B-5**，非本波范围）。
- 1c 仅通过 **`decision_compressor_policy.json`** 管理 DecisionRing 面（D*）与 Compressor 第二档（C*）；见 spike §2–§3.2。

---

## B-3 · 1c 与 `MIMIR_AUTO_EVOLVE` / E-009 分工

| 维度 | **1c** | **AUTO_EVOLVE（E-009）** |
|------|--------|-------------------------|
| 触发 | `MIMIR_AUTO_1C_POLICY=1`（**D3 锁定**，默认关） | `MIMIR_AUTO_ANALYSIS=1` + `MIMIR_AUTO_EVOLVE=1` |
| 时机 | `pipeline_close` 后、与 1b 同阶段（在 analysis 之后或并行只读） | `run_post_analysis_sync` → `apply_evolution_from_analysis` |
| 写入目标 | JSON policy + audit | `skills/<name>/SKILL.md` |
| 建议来源 | `feedback_events` / `tune_audit` 聚合 + artifact **摘要** | LLM analysis `suggestions`（fix/deprecate） |
| 回滚 | 删 policy 文件 | `MIMIR_AUTO_EVOLVE=0` + skills tarball（Gate C closeout） |

**同一次 close 可同时发生：** 1b 写 Top-3、1c 写 policy、AUTO_EVOLVE 写 SKILL — **三者持久化文件不得重叠**（契约 B-2、B-1）。

---

## B-4 · 同 `pipeline_close` 的 nudge 优先级与配额

**执行顺序（固定，供实现与 D3 测试）：**

```text
close_execution_pipeline()
  → (async) run_post_analysis_sync          # analysis artifact；内嵌 apply_evolution_from_analysis 若 AUTO_EVOLVE=1
  → run_tune_after_pipeline_close()         # 1b：Top-3，至多每键 1 nudge/close
  → run_decision_compressor_learn()         # 1c：拟新增；见下配额
```

**1b AutoTuner（现状，不变）：** 每个 `pipeline_close`，每个 Top-3 键 **至多 1 次** `set_override`（`auto_tuner.py` 内按信号分支，可能 0–3 键当次被写，但每键最多一跳）。

**1c 配额（GATE-D2 拍板，实现须遵守）：**

| 子系统 | 每 `pipeline_close` 至多 nudge 键数 | 键集合 |
|--------|-------------------------------------|--------|
| DecisionRing（D*） | **1** | D1–D8 中择一（信号最强者优先） |
| Compressor 第二档（C*） | **1** | C1–C6 中择一 |
| **1c 合计** | **≤2** | 1×D* + 1×C*；无信号则 0 |

**跨轨道优先级（同 close 资源争用时的决策，非执行顺序）：**

1. **1b Top-3** — 先满足退化/工具质量/压缩触发点（已有生产路径，Gate C 已开）。
2. **1c DecisionRing（D*）** — 错误恢复策略；仅在 Top-3 当次未写或信号仍满足时评估（避免与 `compressor.threshold_percent` 同向双跳；若 1b 已下调 percent，1c **不得** 同 close 再 nudge C3/C5 朝「更激进压缩」方向）。
3. **1c Compressor 第二档（C*）** — 在 D* 之后评估；与 Top-3 正交键 only。
4. **AUTO_EVOLVE** — 独立文件；**不参与** Top-3/policy 配额；可与上列同 close 并存。

**冲突消解示例（D3 可测）：** 若 1b 当次写了 `compressor.threshold_percent`，则 1c 同 close **跳过** C1–C6 中任何降低保护、提高压缩侵略性的 nudge（允许 neutral 或 protect 类 nudge 若信号独立，实现期用白名单表）。

---

## B-5 · 禁止项清单

| ID | 禁止行为 | 归属 / 备注 |
|----|----------|-------------|
| F1 | 写/改任意 `skills/**/SKILL.md` | → AUTO_EVOLVE only（B-1） |
| F2 | 写 Top-3 三键入 `tuned_thresholds.json` | → 1b only（B-2） |
| F3 | 运行时改写仓库内 `degeneration_guard.json` **源文件** | guard 仅消费 1b 键 + 静态默认 |
| F4 | 无界新增 `tuned_thresholds._REGISTRY` 键 | Wave 7 不扩 Top-3；新旋钮走 1c policy schema |
| F5 | 1c 调用 `set_override()` | 必须失败或 no-op（contract 断言） |
| F6 | 全量 IntentPredictor / 语义记忆引擎 | §51 可选，非 1c |
| F7 | 无 audit 的 policy 写入 | 每次 nudge 须 `decision_compressor_audit.jsonl` 一行 |
| F8 | §46 签字前合并 1c 实现 PR | Gate D 程序要求 |

---

## B-6 · 快速对照（战略窗 / D3）

```text
SKILL.md          → AUTO_EVOLVE (E-009)
Top-3 三键        → 1b AutoTuner
D1–D8, C1–C6    → 1c policy JSON
每 close：1b ≤3键 | 1c ≤2键(1D+1C) | EVOLVE ≤建议数但每 skill 一次 apply
```

**GATE-D3 contract 草案：** [`iqevo-1c-contract-draft.md`](./iqevo-1c-contract-draft.md)（条文 **1C-01～1C-07** → §49 pytest）。
