# EV-A01 — Agent Core 职责映射（2026-05-24）

> 固定 6 文件；只读审计。交叉：[compressor-overlap-audit](./compressor-overlap-audit.md)、[dead-code-audit](./dead-code-audit.md)（`context_engine` 已删）。

## 摘要

- **配置层** `MimirAetherAgent`（1295 行）委托 **执行层** `MimirAgentLoop.run`（565 行）；tool dispatch 经 adapter → `ExecMixin._execute_single_tool`。
- **整体重叠 ~32%**（2026-05-21 ~35%）：core_loop 变薄后调度重复减轻；prompt 内嵌扫描、压缩预检仍在。
- **附录**：`intent_action_guard` 已接 `agent_loop`；E-012 `jepa_session_hook` 在 `_close_pipeline`；生产预算用 `iteration_budget.EnhancedIterationBudget`，非 `TurnManager`。

## 6 文件职责矩阵

| # | 文件 | 行 | 主职责 | 次要 | import 方（生产） | 重叠 |
|---|------|-----|--------|------|-------------------|:--:|
| 1 | `core_loop.py` | 1295 | 会话/模型/历史/压缩预检；组装 loop | checkpoint、gateway 压缩入口 | `run_agent`、`mimir_cli/task_runner`、`gateway`（经 agent） | 🟡 |
| 2 | `agent_loop.py` | 565 | 纯 tool-calling 循环 `MimirAgentLoop.run` | intent nudge、pipeline 收尾 | **`core_loop` 唯一生产 import** | 🟡 |
| 3 | `turn_loop.py` | 174 | `Turn`/`TurnManager` 单轮状态机 | — | **`__init__` 导出**；生产用 `iteration_budget` | 🟢 |
| 4 | `prompt_builder.py` | 1569 | system prompt、skills、context 文件 | `scan_context_content` 安全扫描 | `core_loop`、`config_mixin`、`gateway/cron`、tools/skills | 🟡 |
| 5 | `recovery_mixin.py` | 268 | 错误恢复、截断、orphan tool 清理 | DecisionRing 联动 | **`core_loop` MRO** | 🟢 |
| 6 | `context_compressor.py` | 877 | 在线压缩 `MimirContextCompressor` | — | **`core_loop`**（预压缩）；gateway `context_compressor` 属性 | 🟢 |

## 关键符号（TOP5 / 文件）

| 文件 | 入口符号 |
|------|----------|
| `core_loop` | `MimirAetherAgent`, `run_conversation`, `run`, `_build_full_messages`, `build_system_prompt` |
| `agent_loop` | `MimirAgentLoop.run`, `_close_pipeline`, `MimirAetherAgentLoop`（测试/薄封装） |
| `turn_loop` | `TurnManager`, `Turn`, `TurnStatus` |
| `prompt_builder` | `build_system_prompt`, `build_system_prompt_parts`, `build_skills_system_prompt`, `scan_context_content`, `load_context_file` |
| `recovery_mixin` | `handle_error_with_recovery`, `_truncate_history`, `_find_safe_truncation_boundary`, `_clean_orphan_tools` |
| `context_compressor` | `MimirContextCompressor.compress`, `should_compress`, `has_content_to_compress`, `ContextCompressorV2` |

## 调用链（Gateway → LLM + tool）

```
Gateway / run_agent / mimir_cli.task_runner
  └─ MimirAetherAgent.run → run_conversation
       ├─ ConfigMixin + prompt_builder.build_system_prompt*  (会话初/刷新)
       ├─ history trim + RecoveryMixin._clean_orphan_tools
       ├─ MimirContextCompressor.compress  (预压缩，loop 内不做)
       ├─ tools.registry schemas + adapters
       └─ MimirAgentLoop.run(messages)
            ├─ model_call → CallersMixin._call_model_with_tokens
            ├─ tool_dispatcher → ExecMixin._execute_single_tool
            ├─ intent_action_guard (nudge / block text-only)
            └─ _close_pipeline → evolution + jepa_session_hook (E-012)
       └─ 回写 conversation_history；EnhancedIterationBudget.consume × turns_used
```

## 重叠度

| 区域 | 文件 | 证据 | 严重度 |
|------|------|------|:--:|
| 消息/turn 调度 | core_loop ↔ agent_loop | `run_conversation` L781–878 委托 `MimirAgentLoop`；历史截断仍在 core | 🟡 |
| 安全扫描 | prompt_builder | `scan_context_content` L57；无独立 `agent/guard/` | 🟡 |
| 压缩触发 | core_loop ↔ compressor | L786–788 `needs_compression`/`compress`；阈值在 compressor | 🟡 |
| mixin 工具执行 | core_loop ↔ exec_mixin | `_tool_dispatcher_adapter` L844–851 → `_execute_single_tool` | 🟡 |

**整体 ~32%**（2026-05-21 ~35%）：微内核委托降低双循环重复；prompt/压缩边界未变。

## vs 2026-05-21

| 项 | 2026-05-21 | 2026-05-24 |
|----|------------|------------|
| `core_loop` | ~2000 | **1295**（−35%） |
| `agent_loop` | ~400 | **565**（+41%，承接执行） |
| 主循环 | 双循环重复 | **已委托** `MimirAgentLoop`；core 保留配置/压缩/历史 |
| E-012 / guard | — | `agent_loop`：intent guard + JEPA post-close（不改 Core 文件边界） |

## Phase 1 建议（不实施）

| 动作 | P0 仍成立？ | 说明 |
|------|:--:|------|
| `orchestrator.py`（core+agent_loop 编排） | **是** | 现边界清晰，适合抽 adapter 层而非再合并类 |
| `prompt_guard` 独立 | **是** | → EV-A05；从 `prompt_builder` 抽 `scan_context_content` |
| `dialogue_mgr` / `engine` | P1 | 历史/会话仍散在 core_loop + mixins |
| `turn_loop` 对齐 | 复核 | 生产走 `EnhancedIterationBudget`；`TurnManager` 或废弃或接 checkpoint |

**附录（3 行）**：`intent_action_guard.py` — agent_loop turn 末；`jepa_session_hook.py` — `_close_pipeline`；mixins `callers/exec/config` — core MRO，工具/registry 在 exec。
