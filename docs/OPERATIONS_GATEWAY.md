# Gateway 运维速查（清单）

面向**人类部署/运维**：约定环境与路径、如何启动、如何验收与看日志。本文**不**包含密钥真值、不代替你在生产机上执行命令。

**Clone / 子模块**：见 [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md) 小节 **「Clone 后必做」**（`git submodule update --init mimicore`），此处不重复。

---

## 1. 环境与路径

| 概念 | 说明 |
|------|------|
| **代码** | 任意 git clone 根（`cli.py`、`gateway/`、`scripts/` 所在目录）。可用 `$(git rev-parse --show-toplevel)` 或 **`MIMIR_REPO_ROOT`**。 |
| **运行时数据根** | **`MIMIR_AETHER_HOME`**（未设置时默认 **`~/.mimiraether`**）。`.env`、`config.yaml`、`data/`、日志等应在此根下解析，与代码根**可分离**。详见 [`path-contract.md`](./path-contract.md)、[`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md)。 |
| **Shell 对齐** | 本地或 systemd `Environment=` 中建议显式设置 `MIMIR_AETHER_HOME` / `HERMES_HOME`；示例见 [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md)。 |

---

## 2. 启动

在**当前仓库根**（含 `cli.py` 的目录）操作：

- **常用入口**：`python3 cli.py gateway start`（与仓库根 [`watchdog.sh`](../watchdog.sh) 内重启命令、[`mimir_prod_smoke.md`](./mimir_prod_smoke.md) 描述一致）。
- **数据根 = 仓库根** 时：可用 [`scripts/start.sh`](../scripts/start.sh)（脚本将 `MIMIR_AETHER_HOME` 默认设为仓库根、`cd` 到该目录后 `exec python3 …/gateway/run.py`；启动前仍会 source **`$MIMIR_AETHER_HOME/.env`**）。

启动前确认 **`$MIMIR_AETHER_HOME/.env`** 与 **`$MIMIR_AETHER_HOME/config.yaml`**（或你环境约定的配置路径）已就位；不要把含密钥的 `.env` 提交进 git。环境变量与 shell 示例见 [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md)。

> **说明**：本仓库**未**提供名为 `scripts/gateway_nohup.sh` 的脚本。若你需要 `nohup … &` 长期驻留，请在自有运维层包装上述命令，并将标准输出/错误重定向到下文 **`$MIMIR_AETHER_HOME/logs/`** 下自管文件（勿写死他人 home 路径）。

---

## 3. 验收（人工）

- **HTTP 健康**：默认常测 `http://127.0.0.1:18999/health`（以你 `config.yaml` / 平台绑定为准；CLI 侧见 [`gateway-cli-health.md`](./gateway-cli-health.md)、[`scripts/smoke_basics.sh`](../scripts/smoke_basics.sh)）。
- **飞书或等价渠道**：发一条真实会话 / 卡片 smoke，确认网关与平台配置联通——**由部署负责人在你方环境执行**；**不要让自动化 Agent 代劳**生产账号操作或代填密钥。

更完整真环境勾选见 [`mimir_prod_smoke.md`](./mimir_prod_smoke.md)。

---

## 4. 日志

以**数据根**为准（即 **`MIMIR_AETHER_HOME`** 解析结果；与 `mimir_constants.get_mimir_home()` / `get_hermes_home()` 对齐时，网关主日志一般为该根下子目录）：

| 用途 | 路径约定（变量形式） |
|------|----------------------|
| 网关运行日志 | **`$MIMIR_AETHER_HOME/logs/gateway.log`**（实现侧见 `mimir_cli/gateway.py` 等；CLI 提示中的 `tail -f` 亦指向数据根下的 `logs/`）。 |
| 仓库根 [`watchdog.sh`](../watchdog.sh) | `LOG_DIR="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}/logs"`，即 **`$MIMIR_AETHER_HOME/logs/watchdog.log`**（脚本内 `LOG_FILE`）。 |

勿臆造未在脚本或代码中出现的子路径；若你自定义了 `LOG_DIR`，以运行环境为准。

---

## 5. systemd / cron（可选）

- **须自行替换**：`WorkingDirectory=` 为你的 **clone 根**；`ExecStart=` 为你的 **`python3` 绝对路径** 与 **venv 内解释器**（若使用 venv）；`User=` / `Group=` 与数据目录权限一致。**禁止**在文档或单元文件示例中写死形如 `/home/某个用户名/...` 的路径。
- **环境文件与变量迁移**：OpenClaw 风格 env 与 `.env` 对齐见 [`GATEWAY_SYSTEMD_ENV.md`](./GATEWAY_SYSTEMD_ENV.md)；与 `start.sh`、systemd `EnvironmentFile=` 的配合见该文「操作步骤」。
- **cron**：若用 cron 调健康检查或拉起脚本，同样把 `cd` 路径与解释器改成**你方** clone 与 venv；避免复制粘贴他人机器路径。

---

## 相关链接

| 文档 / 脚本 | 用途 |
|-------------|------|
| [`path-contract.md`](./path-contract.md) | 仓库根 vs 数据根 |
| [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md) | Shell 变量、`.env` 位置、Clone 后子模块 |
| [`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md) | 独立运行契约 |
| [`gateway-cli-health.md`](./gateway-cli-health.md) | `/health` 与 CLI 健康检查 |
| [`mimir_prod_smoke.md`](./mimir_prod_smoke.md) | 真环境 smoke 清单 |
| [`GATEWAY_SYSTEMD_ENV.md`](./GATEWAY_SYSTEMD_ENV.md) | systemd / `.env` 迁移注意事项 |
