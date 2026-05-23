# EV-A02 — Mimicore 依赖摸底（2026-05-24）

> `rg 'from mimicore|import mimicore' --glob '*.py'`（排除 `mimicore/` 子模块自身）。交叉：[dead-code-audit](./dead-code-audit.md)。

## 摘要

- **17** 个仓库 `.py` 含字面 `mimicore` import（2026-05-21：**17** 行表，含已删的 `cli.py` 顶层）。
- **在线热路径**：`mimir_cli/*`、`api_service.py`、`acp_adapter/*` → `model_defaults`；胶囊 **`tools/mimircore_tool.py`** 经 `sys.path` + `capsule_generator`（非顶层 import）。
- **`cli.py` 14 行 shim** 已不再 import mimicore；依赖迁至 **`mimir_cli/task_runner`**。

## 生产 / 在线（🔴🟡）

| 文件 | 导入 | 时机 | 阻塞启动 |
|------|------|------|:--:|
| `mimir_cli/task_runner.py` | `get_model` | 顶层 | 是（CLI chat 路径） |
| `mimir_cli/chat_runner.py` | `get_model` | `_resolve_model` 内 | 否 |
| `api_service.py` | `get_model`, `get_available_models` | 顶层 | 是（API 进程） |
| `acp_adapter/server.py` | `__version__` | 延迟 | 否 |
| `acp_adapter/session.py` | `load_config` | 延迟 | 否 |
| `tools/mimircore_tool.py` | `capsule_generator`（path 注入） | 工具调用时 | 否 |

## 离线 / 脚本 / 测试（🟢）

`scripts/*`（5）、`run_capsule_*.py`（3）、`activate_self_evolution.py`、`test_fix_2/3`、`migrate_capsules_batch`（注释）。

## vs 2026-05-21

| 变化 | 说明 |
|------|------|
| `cli.py` | 不再 import mimicore（E-008） |
| `skills/.../self_evolution` | 已用本地 `three_ring_architecture`，无 mimicore import |
| 在线阻塞计数 | 仍 **2 类面**：model_defaults + 低频 capsule；均非 agent/gateway 主循环 |

## Phase 1

Mimicore 服务化 **P2**：热路径短、胶囊延迟加载；优先 [agent-core](./agent-core-responsibility-map.md) orchestrator + Memory（A03）。`delegate_tool` 仅读 `mimicore/config/*.yaml` 路径字符串。
