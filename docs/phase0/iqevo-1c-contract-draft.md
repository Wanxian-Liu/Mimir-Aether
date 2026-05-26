# GATE-D3 · 1c tier0 Contract 草案（≥5 条）

| 字段 | 值 |
|------|-----|
| **Date** | 2026-05-27 |
| **Grain** | GATE-D3 / handoff §45 |
| **实现** | §49 `tests/contract/test_horizon_iqevo_wave7_1c.py`（本文件仅草案，**无 pytest**） |
| **分界真源** | [`iqevo-1c-boundary.md`](./iqevo-1c-boundary.md) · [`decision-ring-compressor-1c-spike.md`](./decision-ring-compressor-1c-spike.md) |

---

## 锁定命名（D3 拍板）

| 项 | 锁定值 |
|----|--------|
| **Env 门闩** | `MIMIR_AUTO_1C_POLICY` — 仅 `1` / `true` / `yes`（大小写不敏感）为开；**默认关**（未设或非真值 = 不写入 policy） |
| **Policy 文件** | `$MIMIR_AETHER_HOME/data/decision_compressor_policy.json` |
| **Audit 文件** | `$MIMIR_AETHER_HOME/data/decision_compressor_audit.jsonl` |
| **Learner 入口（拟）** | `agent/decision_compressor_policy.py` → `run_1c_policy_after_pipeline_close()` |
| **Schema 版本** | `schema_version: 1`（根字段，整数） |

### `decision_compressor_policy.json` 最小 schema（v1）

```json
{
  "schema_version": 1,
  "updated_at": "2026-05-27T00:00:00Z",
  "ring": {
    "max_retries": 3,
    "default_backoff_base": 1.0,
    "max_backoff": 60.0,
    "compress_context_pressure": 0.85,
    "truncate_context_pressure": 0.95,
    "confidence_floor": 0.5,
    "rule_priority_bias": {},
    "cooldown_scale": 1.0
  },
  "compressor": {
    "protect_first_n": 3,
    "protect_last_n": 6,
    "summary_target_ratio": 0.20,
    "summary_failure_cooldown_s": 600,
    "preflight_relax_ratio": 0.80,
    "tail_token_budget": 4000
  }
}
```

**禁止顶层或嵌套键（写入时拒绝）：** `compressor.threshold_percent`、`degeneration.loop_detection.threshold`、`tool_quality.degraded_threshold`，及 `tuned_thresholds` / `skills` 等别名。

**有界范围：** 与 spike §2（D1–D8）、§3.1（C1–C6）一致；loader 负责 clamp；越界输入 **拒绝持久化** 并记 audit `rejected=true`。

---

## Contract 表（§49 实现清单）

### 1C-01 · 1c 路径不写 SKILL

| 项 | 内容 |
|----|------|
| **断言** | `run_1c_policy_after_pipeline_close()`（及私有 helper）**不得**调用 `write_skill_md_guarded`、`SkillEvolutionPipeline.evolve_from_suggestions`，且不得在 `skills/` 下创建或修改 `SKILL.md`。 |
| **Boundary** | B-1 · F1 |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_never_writes_skill_md` |
| **失败症状** | 受控 close 后 `skills/` 下出现仅 1c 可解释的 mtime 变更；或 import/mock 显示 1c 模块调用了 skill evolution API。 |

---

### 1C-02 · Top-3 键不得进入 policy 文件

| 项 | 内容 |
|----|------|
| **断言** | 对 `apply_policy_patch()`（或等价）传入含任一顶层的 Top-3 键时，返回 `rejected` 且 **不修改** `decision_compressor_policy.json` 磁盘内容。 |
| **Boundary** | B-2 · F2 |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_rejects_top3_keys_in_policy` |
| **失败症状** | policy JSON 出现 `compressor.threshold_percent` 等键；1c 与 1b 双写同一语义旋钮。 |

---

### 1C-03 · 1c 不得调用 `set_override`（Top-3 通道）

| 项 | 内容 |
|----|------|
| **断言** | 1c learner **不得** import 并调用 `agent.tuned_thresholds.set_override`；调参仅经 policy 文件。 |
| **Boundary** | B-2 · F5 |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_never_calls_set_override` |
| **失败症状** | `tune_audit.jsonl` 出现 `source=1c` 或 1c 堆栈调用 `set_override`；Top-3 被 1c 绕过。 |

---

### 1C-04 · Policy 越界值拒绝持久化

| 项 | 内容 |
|----|------|
| **断言** | 对 `ring.max_retries=99` 或 `compressor.protect_first_n=0` 等超出 spike 有界范围的 patch，loader **拒绝写入** 并保持上一版 policy（或默认）；audit 记录 `rejected=true`。 |
| **Boundary** | B-2（有界）· B-5 F4（无无界扩面） |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_clamps_or_rejects_out_of_range_policy` |
| **失败症状** | policy 文件含非法值导致运行时异常或压缩/恢复行为失控。 |

---

### 1C-05 · 每 `pipeline_close` 至多 2 次 1c nudge（1×D + 1×C）

| 项 | 内容 |
|----|------|
| **断言** | 单次 `run_1c_policy_after_pipeline_close()` 返回的 `applied` 列表长度 **≤2**，且至多 1 个键前缀 `ring.`、至多 1 个前缀 `compressor.`（第二档 C*，**非** `threshold_percent`）。 |
| **Boundary** | B-4 · F7 |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_at_most_two_nudges_per_close` |
| **失败症状** | 同 session 一次 close 产生 3+ 条 `decision_compressor_audit.jsonl` 的 `applied`；或同 close 双跳两个 `ring.*` 键。 |

---

### 1C-06 · `MIMIR_AUTO_1C_POLICY` 默认关，关时不写 policy

| 项 | 内容 |
|----|------|
| **断言** | 未设置 `MIMIR_AUTO_1C_POLICY`（或 `0`/`false`）时，`run_1c_policy_after_pipeline_close()` 返回 `[]` 且 **不创建/不更新** `decision_compressor_policy.json`（允许文件已存在于先前开启）。 |
| **Boundary** | B-3（与 EVOLVE 独立门闩）· F8 程序期默认安全 |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_env_gate_off_by_default` |
| **失败症状** | 新 home 或未配置 env 时 policy/audit 仍增长；§46 前误开 1c 生产写入。 |

---

### 1C-07 · 1c 与 AUTO_EVOLVE 持久化路径不重叠（可选加强）

| 项 | 内容 |
|----|------|
| **断言** | 同一次受控 close（`MIMIR_AUTO_1C_POLICY=1` + `MIMIR_AUTO_EVOLVE=1`）：若 EVOLVE 写了某 `skills/x/SKILL.md`，则 1c 当次 **不得** 修改 `tuned_thresholds.json`，且 policy patch **不得** 含 skills 路径字段。 |
| **Boundary** | B-3 · B-1 |
| **Pytest** | `tests/contract/test_horizon_iqevo_wave7_1c.py::test_1c_and_evolve_disjoint_persistence` |
| **失败症状** | 单模块同时改 SKILL 与 policy；或 1c 写 Top-3 文件。 |

---

## §49 接线检查（实现时）

- [x] `run_1c_policy_after_pipeline_close` 挂在 `execution_pipeline` close 链 **在** `run_tune_after_pipeline_close` **之后**（boundary B-4 顺序）
- [x] `test_horizon_iqevo_wave7_1c.py` 写入 `run_ralph_tier0.sh` Gate2/contract 列表
- [x] `docs/phase0/iqevo-1c-boundary.md` B-3 env 列与本文 `MIMIR_AUTO_1C_POLICY` 一致
- [x] §46 刘哥签字前：contract 可先 **skip/xfail** 实现缺失，但 **不得** 默认 env=1（`1C-06` 门禁；D4 已签 2026-05-27）

---

## Contract ID 索引

`1C-01` · `1C-02` · `1C-03` · `1C-04` · `1C-05` · `1C-06` · `1C-07`（7 条，满足 ≥5）
