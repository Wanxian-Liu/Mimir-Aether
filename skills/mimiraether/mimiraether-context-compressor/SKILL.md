---
auto_load: false
name: mimiraether-context-compressor
description: MimirAether 上下文压缩：本仓库 agent/context_compressor 行为、MimirAetherAgent 参数、Gateway 卫生压缩与配置键（与运行时对齐）。
---

# MimirAether Context Compressor

## 描述

MimirAether 在对话过长时对上下文做**工具输出修剪**与**中间段 LLM/模板摘要**，以控制 token 并保留头尾关键消息。概念借鉴 Hermes；**实现与参数以本仓库代码为准**。

**设计来源（真源）**: 本仓库 [`agent/context_compressor.py`](agent/context_compressor.py)（`ContextCompressorV2`、`HermesStyleCompressor`）。Hermes 上游仅作背景，不替代本路径。

## 核心设计

### 分层保护策略

```
┌─────────────────────────────────────────────────────────────┐
│  HEAD           │  MIDDLE (Compressible) │  TAIL (Protected) │
│  Protected      │  LLM / template summary │  Token-oriented  │
│  ~3 messages    │  Structured summary     │  ~tail_token_budget│
└─────────────────────────────────────────────────────────────┘
```

- **HEAD**：前 `protect_first_n` 条消息（对齐边界时跳过孤立 tool 行），通常含系统与首轮交换。
- **MIDDLE**：`compress_start`～`compress_end` 之间，经 `_generate_summary`（LLM 失败则用模板摘要）。
- **TAIL**：按 `_find_tail_cut_by_tokens` 与 `tail_token_budget`（及 `protect_last_n` 等）保留尾部；**不是**「固定约 20K tokens」——见下文「运行时真源」。

### 两阶段（与 `ContextCompressorV2.compress` 一致）

1. **阶段 1 — 工具输出修剪**（无 LLM）
   - 旧 `role==tool` 且正文长度 **>** `_PRUNED_TOOL_MIN_CHARS`（**200**）的条目替换为占位符（见下表常量）。
2. **阶段 2 — 摘要与重组**
   - 对中间段调用 `_generate_summary`；摘要预算与 `_SUMMARY_RATIO`（20%）等相关；成功则插入一条摘要消息，否则插入简短占位说明。

## 运行时真源

### MimirAetherAgent 使用的压缩器

[`agent/core_loop.py`](agent/core_loop.py) 中构造：

```text
HermesStyleCompressor(
    model=model,
    threshold_percent=0.85,
    protect_first_n=3,
    protect_last_n=6,
    tail_token_budget=4000,
)
```

以上 **`threshold_percent` / `tail_token_budget` 均硬编码**，**不**从仓库根 `config.yaml` 读取。

### ContextCompressorV2 类默认值（直接 `new` 实例时）

与 Agent 传入值不同处已标出。

| 字段 | 类 `__init__` 默认 | MimirAetherAgent 实际传入 |
|------|-------------------|---------------------------|
| `threshold_percent` | **0.50** | **0.85** |
| `protect_first_n` | 3 | 3 |
| `protect_last_n` | **6** | **6** |
| `tail_token_budget` | `None`（则用 `threshold_tokens * summary_target_ratio` 动态算） | **4000** |
| `summary_target_ratio` | 0.20 | 0.20（未改，默认） |
| 初始 `context_length` | 8000 | 由 `core_loop` 在拿到 `model_metadata` 后调用 `compressor.update_model(...)` 覆盖 |

`update_model(model, context_length, ...)` 会重算 `threshold_tokens`、`max_summary_tokens`（见 [`context_compressor.py`](agent/context_compressor.py)）。`MimirAetherAgent` 在 `core_loop.__init__` 中在解析 `_context_length` 后调用 `self.compressor.update_model(...)`（失败时仅 debug 日志）。

### 自动触发：`needs_compression` vs `compress`

- [`needs_compression`](agent/context_compressor.py)：`last_prompt_tokens >= self.threshold_tokens`（来自 `ContextEngine` / `update_from_response` 设计）。
- [`ContextEngine.update_from_response`](agent/context_engine.py) 负责在每轮 API 返回后写入 `last_prompt_tokens`。
- **`core_loop.run_conversation`** 在每轮成功 `_call_model_with_tokens` 后调用 `_compressor_sync_usage_from_llm` → `self.compressor.update_from_response(...)`；`usage` 取自 API 返回（含流式末包），缺省时回退 `model_metadata.estimate_messages_tokens_rough(messages)`。**`compress()`** 内部仍会用 `_estimate_tokens(messages)` 等在**被调用时**做二次判断（见 `compress` 首段条件）。

### `compress()` 内顺序（真函数名）

见 [`ContextCompressorV2.compress`](agent/context_compressor.py)：估算 `display_tokens` → 未达阈值或消息过少则原样返回 → `_prune_old_tool_results` → `_align_boundary_forward` / `_find_tail_cut_by_tokens` → `_generate_summary` → 组装消息 → `_sanitize_tool_pairs`。

### 常量速查（`agent/context_compressor.py`）

| 符号 | 值 / 行为 |
|------|-----------|
| `_PRUNED_TOOL_PLACEHOLDER` | `[Old tool output cleared to save context space]`（**不是**简短版 `[Old tool output cleared]`） |
| `_PRUNED_TOOL_MIN_CHARS` | 200（超过才修剪） |
| `_SUMMARY_RATIO` | 0.20 |
| `_SUMMARY_FAILURE_COOLDOWN` | 600 秒（**10 分钟**）摘要失败冷却 |
| `_MINIMUM_CONTEXT_LENGTH` | `update_model` 时 `threshold_tokens` 下限相关 |
| `SUMMARY_PREFIX` | `[CONTEXT COMPACTION — REFERENCE ONLY]` |

## Gateway 与会话卫生（与 Agent 内压缩分离）

[`gateway/run.py`](gateway/run.py) 在 transcript 过长时可在 **Agent 跑起来之前**做「卫生」压缩（注释说明与 Agent 内压缩分工不同）。

- 从 **`_hermes_home / "config.yaml"`** 读配置（与仓库内示例 [`config.yaml`](config.yaml) **未必是同一文件**）。
- **`compression.enabled`**：仅此布尔（及 truthy 字符串）控制是否启用卫生压缩；路径见代码中 `_hyg_data.get("compression", {})`。
- **卫生触发阈值比例**：代码内 **`_hyg_threshold_pct = 0.85`**（相对解析出的模型上下文长度），**硬编码**，**不是** YAML 键。
- 优先使用 `session_entry.last_prompt_tokens`，否则用 `estimate_messages_tokens_rough(history)`。

## 配置键 → 代码位置（摘要）

| 配置 / 行为 | 读取位置 | 说明 |
|-------------|----------|------|
| `compression.enabled` | `gateway/run.py`（`_hermes_home` 下 `config.yaml`） | 仅 **session hygiene** |
| 卫生 85% 阈值 | 同上，常量 | 非配置项 |
| `model` / `context_length` / `provider` / `base_url` | 同上 | 用于解析上下文长度与运行时；**不**自动驱动 `ContextCompressorV2.update_model` |
| Agent `threshold_percent`、`tail_token_budget` | `agent/core_loop.py` 构造实参 | **硬编码** |

## 结构化摘要模板

下面模板适合**人类撰写**技能文档或与用户对齐期望。

运行时 LLM 摘要使用的节标题见 [`_call_summary_llm`](agent/context_compressor.py) 内嵌 prompt（如 `Pending Asks` 等），与下表**用词可能略有不同**；以代码内模板为生成真源。

```markdown
## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
[User preferences, coding style, constraints]

## Progress
### Done
[Completed work with specific file paths, commands, results]
### In Progress
[Work currently underway]
### Blocked
[Any blockers or issues]

## Key Decisions
[Important technical decisions and why]

## Resolved Questions
[Questions already answered - include answers]

## Pending User Asks
[Unanswered questions/requests - "None." if none]

## Relevant Files
[Files read, modified, created]

## Remaining Work
[What remains - framed as context, not instructions]

## Critical Context
[Specific values, errors, configs]

## Tools & Patterns
[Tools used and effective patterns]
```

## 失败与降级

- 摘要失败：冷却 **`_SUMMARY_FAILURE_COOLDOWN`**（10 分钟）内 `_generate_summary` 早退；可用模板摘要分支。
- `compress` 在无法满足头尾边界时可能**不压缩**并返回原消息（见 `compress_start >= compress_end` 分支）。

## 使用场景

1. **Gateway 卫生压缩**：长会话、大 transcript，受 `compression.enabled` 与 85% 常量阈值约束（见上）。
2. **Agent 循环内**：设计上在 `needs_compression` 为真后调用 `compress`；`last_prompt_tokens` 由每轮 `update_from_response` 更新（见上）。
3. **手动 `/compress`**：`gateway/run.py` 中 `_handle_compress_command` 依赖 `run_agent.AIAgent` 的 `context_compressor` 与 `_compress_context`；`run_agent.AIAgent` 委托至 `MimirAetherAgent.compressor.compress(...)`。

## 已知限制（文档范围外修复）

- 无 API `usage` 且粗估失败时，`last_prompt_tokens` 可能仍为 0，自动触发仍可能偏保守。
- Gateway 卫生压缩仍使用独立配置与 85% 常量阈值，与 Agent 内 `threshold_percent` 等**不一定**数值一致。

---

_概念溯源: Hermes Agent context compressor；实现真源: 本仓库 `agent/context_compressor.py` v2.3 / `HermesStyleCompressor`_
