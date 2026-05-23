# EV-MC04 — 三环闭环实际使用面审计

> **创建**: 2026-05-21 (Mimir, WM-Enhanced)  
> **Backlog**: §2n EV-MC04 `[x]`  
> **方法**: 逐方法标注 × 全仓 grep 调用方

---

## 总览

| 文件 | 行数 | 类 | 方法 | 真调用 | 纸面 |
|------|:--:|:--:|:--:|:--:|:--:|
| `three_ring_architecture.py` | 1,083 | 6 | 36 | **7** | **29** |
| 率 | — | — | — | **19.4%** | **80.6%** |

---

## 逐类审计

### 1. MonitorRing (8 方法 → 2 真调用)

| 方法 | 行 | 被谁调用 | 状态 |
|------|:--:|------|:--:|
| `__init__()` | L94 | `ThreeRingClosedLoop.__init__` | ✅ |
| `set_threshold()` | L121 | 无 | ❌ 纸面 |
| `observe()` | L125 | `skills/.../self_evolution/__init__.py:30` | ✅ |
| `detect_anomalies()` | L150 | `skills/.../self_evolution/__init__.py:35` | ✅ |
| `register_observer()` | L218 | 无 | ❌ 纸面 |
| `notify_observers()` | L222 | 无 | ❌ 纸面 |
| `get_anomaly_history()` | L233 | 无 | ❌ 纸面 |
| `get_status()` | L237 | 无 | ❌ 纸面 |

### 2. DecisionRing (6 方法 → 4 真调用)

| 方法 | 行 | 被谁调用 | 状态 |
|------|:--:|------|:--:|
| `__init__()` | L261 | `ThreeRingClosedLoop.__init__` | ✅ |
| `analyze_root_cause()` | L312 | `skills/.../self_evolution/__init__.py:40` | ✅ |
| `generate_strategies()` | L378 | `skills/.../self_evolution/__init__.py:41` | ✅ |
| `select_best_strategy()` | L424 | `skills/.../self_evolution/__init__.py:55` | ✅ |
| `get_decision_history()` | L482 | 无 | ❌ 纸面 |

### 3. ExecutionRing (6 方法 → 2 真调用)

| 方法 | 行 | 被谁调用 | 状态 |
|------|:--:|------|:--:|
| `__init__()` | L501 | `ThreeRingClosedLoop.__init__` | ✅ |
| `execute()` | L537 | `skills/.../self_evolution/__init__.py:56` | ✅ |
| `verify()` | L607 | `skills/.../self_evolution/__init__.py:65` | ✅ |
| `rollback()` | L631 | 无 | ❌ 纸面 |
| `get_execution_history()` | L820 | 无 | ❌ 纸面 |
| `_exec_*` (15 内部) | L649-811 | 仅在 `execute()` 内部 | ⚠️ 间接 |

### 4. ThreeRingClosedLoop (5 方法 → 0 真调用)

| 方法 | 行 | 被谁调用 | 状态 |
|------|:--:|------|:--:|
| `__init__()` | L842 | `SelfEvolutionSkill.__init__` (仅构造三环子对象) | ✅ |
| `run_cycle()` | L861 | 无 — skill 用自己的 `SelfEvolutionSkill.run_cycle()` | ❌ 纸面 |
| `set_cycle_complete_callback()` | L979 | 无 | ❌ 纸面 |
| `set_escalation_callback()` | L983 | 无 | ❌ 纸面 |
| `get_status()` | L987 | 无 | ❌ 纸面 |
| `run()` | L999 | 无 | ❌ 纸面 |
| `run_continuous()` | L1048 | 无 | ❌ 纸面 |

---

## 关键发现

### 🔴 发现 1: Mimir 有自己的 DecisionRing，不与 Mimicore 重复

`agent/decision_ring.py` (260行) 是 MimirAether 的原生 DecisionRing，用 `DecisionRingConfig` + `DecisionResult` 做错误分类。它在 `core_loop.py:382` 被实例化，在 `recovery_mixin.py` 中被调用。

Mimicore 的 `ThreeRingClosedLoop.decision` 是另一个完全独立的 DecisionRing 实例。两者**零交集**。

### 🔴 发现 2: self_evolution 技能只用 7/36 方法

skill 绕过了 `ThreeRingClosedLoop.run_cycle()` — 用自己的 `SelfEvolutionSkill.run_cycle()` 直接调用子对象方法。这意味着 `ThreeRingClosedLoop` 的 7 个方法（run_cycle/run/run_continuous/get_status/callbacks）全部是纸面架构。

### 🟡 发现 3: ExecutionRing 的 15 个 _exec_* 方法全部通过 execute() 间接调用

`ExecutionRing.execute()` L537-606 包含一个策略→方法映射字典，将策略名路由到对应的 `_exec_*` 方法。这 15 个方法虽然不被外部直接调用，但通过 `execute()` 可达。它们是**设计良好的扩展点**，但实际从未被 route 触发过（因为 Mimir 从未完整跑过 self_evolution 闭环）。

---

## 实际依赖链（从 Mimir 到 Mimicore）

```
skills/mimiraether/mimiraether-self_evolution/__init__.py
    ├─ MonitorRing.observe()
    ├─ MonitorRing.detect_anomalies()
    ├─ DecisionRing.analyze_root_cause()
    ├─ DecisionRing.generate_strategies()
    ├─ DecisionRing.select_best_strategy()
    ├─ ExecutionRing.execute()
    └─ ExecutionRing.verify()

这 7 个调用全部在 SelfEvolutionSkill 的 5 个方法中
(collect_metrics / analyze_gaps / execute_improvement / verify_result / run_cycle)
```

---

## 提炼影响

| 决策 | 说明 |
|------|------|
| **ThreeRingClosedLoop 可大幅删减** | 7/36 方法被调用。run_cycle/run/run_continuous/get_status/callbacks 全部删除。MonitorRing 的 observer/status 方法删除。 |
| **ExecutionRing._exec_* 保留** | 虽当前未触发，但 execute() 的路由逻辑是正确的扩展点 |
| **三环不接入 agent loop** | Mimir 有自己的 DecisionRing (`agent/decision_ring.py`)，与 Mimicore 三环无关 |

---

> **下一粒**: EV-MC05 — 提取边界精确设计  
> **签收**: Mimir WM-Enhanced  
> **tier0**: 本粒纯只读
