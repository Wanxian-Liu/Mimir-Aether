# MimirAether 运行契约（去平台依赖）

独立部署时建议显式设置环境变量，避免隐式依赖 `~/.openclaw/`。

## 必填 / 强烈推荐

| 变量 | 说明 |
|------|------|
| `MIMIR_AETHER_HOME` | 本仓库根目录（含 `config.yaml`、`.env`、`skills/`）。**生产环境推荐始终设置。** 与旧名 `MIMIRAETHER_HOME` 同时存在时，**以本变量为准**。 |
| `HERMES_HOME` | 与 `MIMIR_AETHER_HOME` **设为同一路径**，直到所有 `hermes_cli` / `hermes_constants` 调用路径完全收敛。`scripts/start.sh` 会自动对齐。 |

未设置 `MIMIR_AETHER_HOME` 时，代码默认回退到 `~/.openclaw/projects/MimirAether`（与历史布局兼容）。

## 配置与密钥

- **主配置**：`$MIMIR_AETHER_HOME/config.yaml`
- **密钥**：`$MIMIR_AETHER_HOME/.env`（勿提交真实密钥；见仓库根 `.env.example`；从平台 `gateway.systemd.env` 迁移见 [`GATEWAY_SYSTEMD_ENV.md`](./GATEWAY_SYSTEMD_ENV.md)）

## 与 OpenClaw 平台层的关系

- 不再要求存在 `~/.openclaw/config.yaml` 才能运行 MimirAether；若仍保留该文件，请注意与项目内 `config.yaml` 可能重复，以 **`MIMIR_AETHER_HOME` 树下文件为准**。
- 遗留变量 `OPENCLAW_*`：若仍有消费方，视为过渡兼容；新代码不应新增依赖。详见 [`OPENCLAW_ENV_LEGACY.md`](./OPENCLAW_ENV_LEGACY.md)。

## vendored `hermes_cli`

`hermes_cli/` 目录为自包含副本（MIT，来源见 `NOTICE`），供 `mimcore` 与 `agent/auxiliary_client` 等 import，**无需**将外部 `hermes-agent` 加入 `PYTHONPATH`。

闭包与入口模块清单见 `docs/hermes_cli_closure.md`。
