# hermes_cli 闭包（MimirAether 侧引用基线）

本仓库内 **直接** `from hermes_cli` / `import hermes_cli` 的位置（用于验收与变更审计）。完整 **`hermes_cli/`** 包已 vendoring 至仓库根目录，内部子模块互引见上游树状结构。

## 本仓库直接引用

| 模块 | 消费方 |
|------|--------|
| `hermes_cli.auth` | `agent/auxiliary_client.py`, `tools/managed_tool_gateway.py`, `mimcore/auth.py` |
| `hermes_cli.config` | `mimcore/config.py`（re-export） |
| `hermes_cli.models` | `agent/auxiliary_client.py` |
| `hermes_cli.model_normalize` | `agent/auxiliary_client.py` |
| `hermes_cli.runtime_provider` | `agent/auxiliary_client.py` |

## 与本仓库其他顶层模块的耦合（vendored `hermes_cli` 内部）

vendored 包内多处 `from hermes_constants import ...`，使用本仓库根目录的 [`hermes_constants.py`](../hermes_constants.py)（需与 `MIMIR_AETHER_HOME` / `HERMES_HOME` 契约一致）。

部分文件延迟导入 `hermes_state`、`hermes_logging`（本仓库根目录已有实现）。

## 重新生成引用列表

```bash
./scripts/print_hermes_cli_imports.py
```
