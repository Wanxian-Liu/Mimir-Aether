# 从 `gateway.systemd.env` 迁移到 MimirAether `.env`

OpenClaw 平台层常用 `~/.openclaw/gateway.systemd.env` 注入密钥。独立运行时应改为 **项目根** 的 `.env`（与 `docs/MIMIR_RUNTIME_CONTRACT.md` 一致）。

## 建议对齐的变量

| 典型 platform env | 项目 `.env` 键 | 说明 |
|-------------------|----------------|------|
| `DEEPSEEK_API_KEYS` | 见下文「密钥变量对照」 | OpenClaw 常见写法是逗号分隔多 key；本仓库**不会**自动把该变量当作轮换池读取。 |
| `TAVILY_API_KEY` | `TAVILY_API_KEY` | 同上。 |
| （其他） | 同名复制 | 凡 gateway / agent 已读的变量，按名写入 `.env`。 |

## 环境变量 → 消费方（DeepSeek / 辅助模型）

下列为运维最常混淆的 **DeepSeek** 相关名；其它 provider 一般与 `hermes_cli.auth` 里 `ProviderConfig.api_key_env_vars` 一致（见 [`hermes_cli/auth.py`](../hermes_cli/auth.py) 中各 provider 定义）。

| 变量名 | 是否由本仓库读取 | 主要消费位置 / 行为 |
|--------|------------------|---------------------|
| `DEEPSEEK_API_KEY` | **是** | **主路径**：`hermes_cli.auth` 在解析 `deepseek` provider 时通过 `get_env_value("DEEPSEEK_API_KEY")` 取密钥（与 `os.environ`、项目 `.env` 合并，见 `hermes_cli.config`）。**Agent 主循环** [`agent/core_loop.py`](../agent/core_loop.py) 在模型选择与直连 DeepSeek 时读取 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`。**凭证池** [`agent/credential_pool.py`](../agent/credential_pool.py) 将 `DEEPSEEK_API_KEY` 列为可托管的环境名之一。**CLI / 工具**：[`cli.py`](../cli.py)、[`mimir_cli/doctor.py`](../mimir_cli/doctor.py)、[`run_service.py`](../run_service.py)、[`precipitate.py`](../precipitate.py)、[`scheduler/tasks/learn_and_evolve_8h.py`](../scheduler/tasks/learn_and_evolve_8h.py)、[`mimicore/utils/deepseek_client.py`](../mimicore/utils/deepseek_client.py) 等仅认 **`DEEPSEEK_API_KEY`**（单名）。 |
| `DEEPSEEK_API_KEYS` | **否**（本仓库未解析） | 仅作从旧平台迁移时的**文档/示例**提示（见根目录 [`.env.example`](../.env.example) 注释）。`hermes_cli.auth` 的 DeepSeek 配置**只**声明 `("DEEPSEEK_API_KEY",)`，不会遍历逗号分隔多 key。若你过去使用 `DEEPSEEK_API_KEYS=key1,key2`，请在 `.env` 中改为 **`DEEPSEEK_API_KEY=...`**（任选一个当前要用的 key），或自行在外层做 key 轮换后再注入单一 `DEEPSEEK_API_KEY`。 |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_API_BASE` | **是**（视调用路径） | `hermes_cli.auth` / provider 使用 `DEEPSEEK_BASE_URL`；部分脚本与 [`cli.py`](../cli.py) 亦识别 `DEEPSEEK_API_BASE`，二者若同时存在以具体模块为准，建议统一为 `DEEPSEEK_BASE_URL`。 |
| `OPENROUTER_API_KEY` | **是**（作聚合/回退） | 当主模型走 OpenRouter 上的 DeepSeek 等时，[`agent/core_loop.py`](../agent/core_loop.py) 会在缺少 `DEEPSEEK_API_KEY` 时用 `OPENROUTER_API_KEY` 等作回退（见该文件内 provider 分支）。**辅助侧任务**路由见 [`agent/auxiliary_client.py`](../agent/auxiliary_client.py)（按 OpenRouter → Nous → custom → … 顺序，不单独解析 `DEEPSEEK_API_KEYS`）。 |

**小结**：独立部署时请在 **`$MIMIR_AETHER_HOME/.env`** 中提供 **`DEEPSEEK_API_KEY`**（单 key）；不要把多 key 轮换寄托在 `DEEPSEEK_API_KEYS` 上，除非你在 systemd/容器入口自行拆成单一变量再启动进程。

## 操作步骤

1. 复制 `gateway.systemd.env` 中**非注释**行到 `$MIMIR_AETHER_HOME/.env`（勿提交仓库）。
2. 使用 [`scripts/start.sh`](../scripts/start.sh) 或 systemd 单元内 `EnvironmentFile=` 指向该 `.env`。
3. 设置 `MIMIR_AETHER_HOME` 与 `HERMES_HOME`（`start.sh` 默认将二者设为仓库根）。
