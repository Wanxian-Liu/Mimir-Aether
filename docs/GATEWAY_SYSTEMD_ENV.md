# 从 `gateway.systemd.env` 迁移到 MimirAether `.env`

OpenClaw 平台层常用 `~/.openclaw/gateway.systemd.env` 注入密钥。独立运行时应改为 **项目根** 的 `.env`（与 `docs/MIMIR_RUNTIME_CONTRACT.md` 一致）。

## 建议对齐的变量

| 典型 platform env | 项目 `.env` 键 | 说明 |
|-------------------|----------------|------|
| `DEEPSEEK_API_KEYS` | `DEEPSEEK_API_KEY` 或保留多 key 名 | 上游 `hermes_cli.auth` 多解析 `DEEPSEEK_API_KEY`；若你使用逗号分隔多 key，可继续用 `DEEPSEEK_API_KEYS` 若工具链已支持（以 `agent/auxiliary_client` 实际解析为准）。 |
| `TAVILY_API_KEY` | `TAVILY_API_KEY` | 同上。 |
| （其他） | 同名复制 | 凡 gateway / agent 已读的变量，按名写入 `.env`。 |

## 操作步骤

1. 复制 `gateway.systemd.env` 中**非注释**行到 `$MIMIR_AETHER_HOME/.env`（勿提交仓库）。
2. 使用 [`scripts/start.sh`](../scripts/start.sh) 或 systemd 单元内 `EnvironmentFile=` 指向该 `.env`。
3. 设置 `MIMIR_AETHER_HOME` 与 `HERMES_HOME`（`start.sh` 默认将二者设为仓库根）。
