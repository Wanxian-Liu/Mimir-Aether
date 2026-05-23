# Mimir → Mimicore Import 精确审计

> **来源**: EV-MC01（Backlog §2n）
> **方法**: `grep -rn 'from mimicore\|import mimicore' --exclude-dir=mimicore` 全仓库扫描
> **日期**: 2026-05-21 (Mimir WM-Enhanced)
> **状态**: ✅ 100% import 清单完成

---

## 1. 总览

| 类别 | 数量 | 说明 |
|------|:--:|------|
| **运行时 (Online)** | **6** | Mimir 生产环境实际执行 |
| **脚本 (Offline)** | **9** | 离线脚本/一次性工具 |
| **测试/死引用 (L3)** | **2** | Mimicore L3 层引用，Mimir 生产环境不触发 |
| **字符串引用** | **1** | `cli.py:959` — 诊断检查列表，非 import |
| **总计** | **18** | |

---

## 2. 运行时 import 清单（6 个 — 在线 · 生产环境触发）

### 2.1 `cli.py:38` — model_defaults (8 次 + 2 次调用)

```
from mimicore.config.model_defaults import get_model, get_available_models, DEFAULT_MODEL as MIMIR_DEFAULT_MODEL
```

| 符号 | 代码中调用次数 | 调用行 |
|------|:--:|------|
| `get_model()` | **8** | L92 / L457 / L515 / L1165 / L1507 / L1681 / L1753 / L2511 |
| `get_available_models()` | **2** | L1674 / L1749 |
| `MIMIR_DEFAULT_MODEL` | 0 | 导入但未直接使用 — 始终调用 `get_model()` |

**触发路径**: `cli.py` 启动 → 顶层 import → 模型解析（50 行 `model_defaults.py`）
**数据类型**: L1 — Mimir 核心依赖

---

### 2.2 `api_service.py:31` — model_defaults (5 次调用)

```
from mimicore.config.model_defaults import get_model, get_available_models, DEFAULT_MODEL as MIMIR_DEFAULT_MODEL
```

| 符号 | 调用次数 | 调用行 |
|------|:--:|------|
| `get_model()` | **5** | L161 / L230 / L421 / L458 / L617 |

**触发路径**: Gateway → API 请求 → 模型解析
**数据类型**: L1 — Mimir 核心依赖

---

### 2.3 `tools/mimircore_tool.py:248` — CapsuleGenerator + CapsuleType (惰性导入)

```
from mimicore.capsule_generator import CapsuleGenerator, CapsuleType
```

| 符号 | 调用行 | 说明 |
|------|------|------|
| `CapsuleGenerator()` | L258 | 实例化 → `generate_capsule()` |
| `CapsuleType.INNOVATE/OPTIMIZE/REPAIR` | L252-254 | 胶囊类型映射 |

**触发路径**: Mimir 调用 `produce_capsule` 工具 → 惰性 import → CapsuleGenerator(911行)
**调用频率**: 低 — 仅在刘哥/琬弦手动执行胶囊生成时触发
**数据类型**: L1 — Mimir 核心依赖

---

### 2.4 `skills/mimiraether/mimiraether-self_evolution/__init__.py:14` — ThreeRingClosedLoop

```
from mimicore.evolve.three_ring_architecture import ThreeRingClosedLoop
```

| 符号 | 调用行 | 说明 |
|------|------|------|
| `ThreeRingClosedLoop()` | L25 | 实例化 |
| `monitor.observe()` / `detect_anomalies()` | L30 / L35 | 监控环 |
| `decision.analyze_root_cause()` / `generate_strategies()` | L40-41 | 决策环 |
| `decision.select_best_strategy()` | L55 | 策略选择 |
| `execution.execute()` | L56 | 执行环 |

**触发路径**: Mimir 加载 `self_evolution` 技能 → import → 1083 行三环架构
**调用频率**: 极低 — self_evolution 技能当前是空壳，从未在生产环境完成过完整闭环
**数据类型**: L1 — Mimir 核心依赖（但实际使用面极窄，见 EV-MC04）

---

### 2.5 `acp_adapter/server.py:65` — __version__

```
from mimicore import __version__ as MIMIRAETHER_VERSION
```

| 符号 | 调用行 | 说明 |
|------|------|------|
| `MIMIRAETHER_VERSION` | L247 / L671 | Agent 信息 + 启动日志 |

**触发路径**: ACP 适配器进程启动 → import mimicore `__version__`
**数据类型**: L1 — 单行字符串依赖（`mimicore/__init__.py: __version__ = "0.1.0"`）

---

### 2.6 `acp_adapter/session.py:434` — load_config

```
from mimicore.config.loader import load_config
```

| 符号 | 调用行 | 说明 |
|------|------|------|
| `load_config()` | L437 | → `config = load_config()` |

**触发路径**: ACP 适配器会话初始化 → 惰性 import → 配置加载
**数据类型**: L1 — ~100 行配置加载器

---

## 3. 离线脚本 import 清单（9 个 — 不触发 Mimir 运行时）

| # | 文件 | 行 | 导入内容 | L1/L2 |
|---|------|:--:|------|:--:|
| 1 | `run_capsule_mimir_hermes.py` | 12 | `CapsuleGenerator, CapsuleType` | L2 |
| 2 | `run_capsule_script.py` | 13 | `CapsuleGenerator` | L2 |
| 3 | `run_subagent_capsule.py` | 13 | `CapsuleGenerator` | L2 |
| 4 | `scripts/diag_capsule.py` | 19 | `CapsuleGenerator, GeneMapper, GeneType, Capsule` | L2 |
| 5 | `scripts/step3_append_generate_and_evaluate.py` | 150 | `CapsuleGenerator` | L2 |
| 6 | `scripts/gen_and_score.py` | 42 | `CapsuleGenerator` | L2 |
| 7 | `scripts/eval_capsule_gdi.py` | 41 | `CapsuleGenerator` | L2 |
| 8 | `activate_self_evolution.py` | 37 | `ThreeRingClosedLoop` | L2 |
| 9 | `activate_self_evolution.py` | 45 | `SelfDriveEngine` | L2 |

**说明**: 全部是离线脚本的顶层/lazy import。Mimir 运行时不会加载这些脚本。如果提炼 Mimicore，这些脚本的 import 路径同步更新即可（机械替换）。

---

## 4. L3 层引用（2 个 — Mimir 生产环境不触发）

| # | 文件 | 行 | 导入内容 | Mimicore 层 |
|---|------|:--:|------|:--:|
| 1 | `test_fix_2_dangerous_cmd.py` | 11 | `from mimicore.mini_agent.hooks import DefaultBeforeToolCallHook, HookContext, ToolCall` | L3 — mini_agent (Mimir 从未调用) |
| 2 | `test_fix_3_fence.py` | 11 | `from mimicore.gateway.gateway import fence_checkpoint` | L3 — gateway (Mimicore 自己的 gateway) |

**说明**: 两个文件都是测试文件（`test_fix_*.py`），且引用的模块属于 Mimicore 自己的 L3 层（mini_agent / mimicore的gateway）。Mimir 生产环境绝不可能触发这些 import。

---

## 5. 字符串引用（1 个 — 非 import）

| 文件 | 行 | 内容 |
|------|:--:|------|
| `cli.py` | 959 | `"mimicore.config.model_defaults"` — 诊断检查列表中的模块名字符串，用于 `importlib.import_module()` 做可用性检查 |

**说明**: 这是一个模块名**字符串**，不是 import 语句。如果提炼后删除 `mimicore/config/model_defaults.py`，需要同步更新这个字符串。

---

## 6. 依赖图谱（运行时 6 个 import 的 Mimicore 内部依赖）

```
cli.py (8×get_model) ─────────┐
api_service.py (5×get_model) ─┤─── mimicore/config/model_defaults.py (50行)
                               │        依赖: 无内部 Mimicore 依赖 (独立)
                               │
tools/mimircore_tool.py ───────┤─── mimicore/capsule_generator.py (911行)
                               │        依赖: gdi_scorer.py (453行)
                               │              evomap_validator.py (674行)
                               │              gene_mapper.py (325行)
                               │
self_evolution skill ──────────┤─── mimicore/evolve/three_ring_architecture.py (1083行)
                               │        依赖: monitor_collector / feedback_orchestrator
                               │              decision_ring / execution_ring
                               │
acp_adapter/server.py ─────────┤─── mimicore/__init__.py (1行: __version__)
                               │
acp_adapter/session.py ────────┘─── mimicore/config/loader.py (~100行)
```

---

## 7. 关键发现

| # | 发现 | 说明 |
|---|------|------|
| 1 | **运行时依赖只有 6 个点** | 全部是 L1 层（~3,500 行），证实了提炼方案的 Precondition |
| 2 | **model_defaults.py 是调用最频繁的** | `cli.py` 8 次 + `api_service.py` 5 次 = 13 次。只有 50 行，三方案里架构方向二建议内联是对的 |
| 3 | **CapsuleGenerator 通过惰性 import 调用** | 只有手动触发 `produce_capsule` 工具时才 import，日常 Mimir 推理不会加载 911 行 |
| 4 | **ThreeRingClosedLoop 的 self_evolution skill 是空壳** | import 存在但从未在生产环境完成完整闭环 — EV-MC04 会确认 |
| 5 | **acp_adapter 只用了 __version__ + load_config** | 一个 1 行字符串 + 一个 ~100 行配置加载器。提炼成本极低 |
| 6 | **L3 引用仅出现在 test_fix 文件** | Mimir 生产环境绝不触发。这两个测试文件即使删除也不影响 tier0 |
| 7 | **9 个离线脚本的 import 全部指向 L1 CapsuleGenerator** | 提炼后脚本 import 路径机械替换即可 |
| 8 | **零循环依赖** | 6 个运行时 import 的 Mimicore 内部没有引回 Mimir |

---

## 8. 提取优先级（按提炼难度 × 频率排序）

| 优先级 | import | 难度 | 原因 |
|:--:|------|:--:|------|
| **P0** | `model_defaults.py` (cli + api_service) | 低 | 50 行纯函数，无内部依赖，13 次调用频率最高 |
| **P1** | `__version__` (acp server) | 极低 | 1 行字符串，可直接内联 |
| **P2** | `load_config` (acp session) | 低 | ~100 行，惰性 import |
| **P3** | `CapsuleGenerator` (mimircore_tool) | 中 | 911 行 + 3 个内部依赖(1452行)，惰性 import 降低风险 |
| **P4** | `ThreeRingClosedLoop` (self_evolution) | 高 | 1083 行 + 多个内部依赖，且当前是空壳 |

---

> **下一粒**: EV-MC02 — L2 零触碰验证（12 目录 grep=0）  
> **签收**: Mimir WM-Enhanced（IC 安全门活跃）  
> **tier0**: 181+2 PASS（本轮纯只读，无代码改动）
