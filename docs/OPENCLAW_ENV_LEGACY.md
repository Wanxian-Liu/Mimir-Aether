# 遗留 `OPENCLAW_*` 环境变量（过渡）

> **Canonical alias table:** [`docs/adr/003-runtime-env-aliases.md`](./adr/003-runtime-env-aliases.md) (ADR-003). This file is a short index; ADR-003 supersedes scattered notes.

独立化后，**新逻辑**以 `MIMIR_AETHER_HOME` / `get_mimir_home()` 与项目树下 `config.yaml`、`.env` 为准。下列变量若仍存在，多为历史兼容；新功能不应再增加依赖。

| 变量 | 仍可能被消费的位置 | 说明 |
|------|---------------------|------|
| `OPENCLAW_GATEWAY_LOCK_DIR` | [`gateway/status.py`](../gateway/status.py) `_get_lock_dir()` | 若设置，覆盖默认的 `data/gateway-locks`。 |
| `OPENCLAW_SESSION_DB` | `mimir_constants.get_mimir_session_search_db_path()` | Legacy read; prefer **`MIMIR_SESSION_DB`**. |
| （其他 `OPENCLAW_*`） | 零散注释或未迁移脚本 | 见 ADR-003；禁止新增 reader。 |

检索命令示例：

```bash
rg 'OPENCLAW_' --glob '*.py' --glob '!hermes_cli/**'
```
