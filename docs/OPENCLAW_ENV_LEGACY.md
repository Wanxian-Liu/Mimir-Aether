# 遗留 `OPENCLAW_*` 环境变量（过渡）

独立化后，**新逻辑**以 `MIMIR_AETHER_HOME` / `HERMES_HOME` 与项目树下 `config.yaml`、`.env` 为准。下列变量若仍存在，多为历史兼容；新功能不应再增加依赖。

| 变量 | 仍可能被消费的位置 | 说明 |
|------|---------------------|------|
| `OPENCLAW_GATEWAY_LOCK_DIR` | [`gateway/status.py`](../gateway/status.py) `_get_lock_dir()` | 若设置，覆盖默认的 `data/gateway-locks`。 |
| （其他 `OPENCLAW_*`） | 零散注释或未迁移脚本 | 以代码检索为准；计划逐步删除或文档化。 |

检索命令示例：

```bash
rg 'OPENCLAW_' --glob '*.py' --glob '!hermes_cli/**'
```
