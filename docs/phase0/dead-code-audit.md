# EV-P03 — 废弃代码审计（2026-05-24）

> 方法：全仓库 `rg`（只读）；未改 `agent/` / `gateway/` / `mimir_cli/` 的 `.py`。  
> **判定**：`import` / 动态 import **>0** → 不可删；仅 docs/skills → 文档漂移；仅 fixtures 样板 → 低优先级。

## 摘要

- **不可删**：`tools/registry.py` 及 agent 侧 5 处 `import tools.registry`；`cli.py` 薄 shim + tier0 语法清单仍列名。
- **安全可删 / Phase 1+**：`tests/fixtures/example_fixture.py`（零引用样板）；9 个 `agent/*.py` 零包内 import（见 #8）。
- **文档漂移**：`agent/context_engine.py` **不存在**；skills/docs 仍写旧路径；`agent/tool_registry.py` 已弃用，运行时代码走 `tools.registry`。

## 必查项

| # | 目标 | 路径 / 引用数 | 判定 |
|---|------|----------------|------|
| 1 | `tools/registry` · `agent/tool_registry` | `tools/registry`：**37** 文件 `from/import tools.registry`；agent 生产代码 **5** 处（callers/config/exec/core_loop×2）。`agent/tool_registry.py`：生产 **0** import，仅 `agent/test_tool_registry_*.py`（2） | 不可删（`tools.registry`）；`agent/tool_registry` → Phase 1+ 收敛 |
| 2 | `context_engine.py` | 文件 **无**；`rg agent/context_engine` → skills/docs **8+** 处；运行时用 `plugins.context_engine` / `mimir_cli/plugins_cmd.py` | 文档漂移 |
| 3 | `cli.py` vs `mimir_cli/` | `cli.py` **14** 行 shim → `mimir_cli.main`；`run_ralph_tier0.sh` Gate1 仍含 `cli.py`；`mimir_cli/main.py` **~6052** 行真入口 | 不可删 shim；D7「删 cli.py」→ **已薄化**，彻底移除需 Phase 1 兼容公告 |
| 4 | `example_fixture` | `tests/fixtures/example_fixture.py`；全仓库 **0** import | 样板 / Phase 1 接入或删 |
| 5 | `_archive/` · `archive/` · `learnings/` | `_archive/` **无**；`archive/**/*.py` **2**（hermes_tasks）；`learnings/**/*.py` **0**；均无运行 `import` | 豁免区，非运行时代码 |
| 6 | 可疑串 | `{"content": "#!`、`{"content": "\"\"\"\nTaskLoop` → **0** 匹配（`.py`/数据）；`TaskLoop` 仅在 `scripts/task_loop*.py` 等正常模块 | 与 2026-05-21 一致：不存在 |
| 7 | 自发现 TOP3 orphan `agent/*.py` | `memory_system.py`（540 行，**0** `from/import agent.memory_system`）；`auxiliary_client_new.py`（197）；`chat_interface.py`（241） | Phase 1+ 归档或接线 |
| 8 | （汇总） | 非 `test_*` 的 `agent/*.py` 中 **9** 模块零包引用（含 `memory_provider`、`session_manager` 等） | 低优先级清理候选 |

## 与 2026-05-21（GOD § EV-P03）差异

| 项 | 2026-05-21 | 2026-05-24 |
|----|------------|------------|
| `tools.registry` agent 引用 | 5 处 | **仍 5 处**；全仓扩至 **37** 文件 |
| `cli.py` | GOD 表 5836 行「计划删除」 | **E-008 薄 shim 14 行**；逻辑在 `mimir_cli/` |
| `context_engine.py` | 未单独记 | **文件缺失**，skills 仍引用 → 新增漂移项 |
| 异常 JSON 串 | 无匹配 | **仍无** |
| `agent/tool_registry.py` | 「可删」争议 | 运行时不 import；**tier0 仍编译检查** |

## Phase 1 建议（不实施）

1. **cli.py**：文档统一 `python -m mimir_cli` / `mimir`；评估从 tier0 清单移除前保留 shim 一版。  
2. **context_engine**：批量改 skills 链到 `plugins/context_engine/` 或删除 `agent/context_engine.py` 叙述。  
3. **orphan agent 模块**：对 TOP3 做「删除 vs 接入 core_loop/memory」决策；`example_fixture` 与 `tests/agent/conftest` 二选一合并。
