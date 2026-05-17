# MimirAether — 旧环境下线清单（人工对照）

| 字段 | 值 |
|------|-----|
| **状态** | 理清期运维清单（**仅文档**；由负责人在离机前 / 换凭证后手工执行） |
| **依据** | [`MIMIR_CLARIFY_BASELINE.md`](./MIMIR_CLARIFY_BASELINE.md) §1–2、§5，[`MIMIR_OPENCLAW_BOUNDARY.md`](./MIMIR_OPENCLAW_BOUNDARY.md)，[`path-contract.md`](./path-contract.md)，[`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) |
| **真源（上线后仅保留）** | 代码：**`~/src/MimirAether`**（或你的 `MIMIR_REPO_ROOT`）；数据：**`$MIMIR_AETHER_HOME`**（默认 `~/.mimiraether`） |

---

## 1. 目的

在**换飞书应用 / 换机器 / 离机维护**前后，用本清单确认：**旧 MA 镜像与 OpenClaw 并行网关不会再被拉起**，避免双网关、双飞书应用、旧路径 cron/watchdog 自动复活。

**原则**

- **只保留**一条生产链路：`{git clone 根}` + `$MIMIR_AETHER_HOME`（见 [`path-contract.md`](./path-contract.md)）。
- **删除用户目录前必须先备份**（至少：`$MIMIR_AETHER_HOME/.env`、`config.yaml`、`data/`、`memory/`、`logs/`）；本清单**不**替你执行 `rm -rf`。
- **不修改**你机器上的 systemd/cron（下文仅给出**供人复制执行**的命令示例）；Agent **不得**代跑生产停服或改单元文件。

**边界提醒**（详见 T03）：`~/.openclaw/projects/MimirAether` 为**归档/只读对照**，不是代码或数据真源；**不得**从此目录启动 gateway 或写入 `.env`。

---

## 2. 检查表

每项格式：**如何查** → **如何停** → **验收**。将 `~/src/MimirAether`、`~/.mimiraether` 替换为你方实际路径。

### 2.1 旧 OpenClaw 项目目录下的 gateway

| 步骤 | 操作 |
|------|------|
| **如何查** | `test -d ~/.openclaw/projects/MimirAether && pgrep -af 'gateway/run.py' \| grep -F '.openclaw/projects/MimirAether'` |
| **如何停** | 对查到的 PID：`kill <pid>`；若由该目录下脚本拉起，勿再执行 `cd ~/.openclaw/projects/MimirAether && python3 gateway/run.py` 或 `cli.py gateway start` |
| **验收** | 上列 `pgrep` **无输出**；生产启动命令仅指向 **`$MIMIR_REPO_ROOT`**（如 `~/src/MimirAether`） |

### 2.2 `openclaw-gateway.service`（若存在）

| 步骤 | 操作 |
|------|------|
| **如何查** | `systemctl --user list-unit-files 'openclaw-gateway*' 2>/dev/null; systemctl list-unit-files 'openclaw-gateway*' 2>/dev/null`；`systemctl status openclaw-gateway.service 2>/dev/null` |
| **如何停** | `sudo systemctl stop openclaw-gateway.service`；`sudo systemctl disable openclaw-gateway.service`（user 单元则加 `--user`） |
| **验收** | `systemctl is-active openclaw-gateway.service` 为 **inactive**；`is-enabled` 为 **disabled**（或单元文件已移除） |

### 2.3 cron / watchdog 指向旧路径

| 步骤 | 操作 |
|------|------|
| **如何查** | `crontab -l 2>/dev/null; ls /etc/cron.d/ 2>/dev/null`；`grep -rE 'openclaw/projects/MimirAether|\.openclaw/projects' ~/.config/systemd/user/ /etc/systemd/system/ 2>/dev/null`；检查是否仍有 cron 调用**旧 clone** 的 `watchdog.sh` / `gateway start` |
| **如何停** | 编辑 `crontab -e`：删除或注释含 `~/.openclaw/projects/MimirAether` 的行；将 watchdog 改为 **`$MIMIR_REPO_ROOT/watchdog.sh`** 且 `Environment=MIMIR_AETHER_HOME=...` 指向数据根 |
| **验收** | `crontab -l` 与 systemd timer（若有）中**无**旧项目路径；[`watchdog.sh`](../watchdog.sh) 的 `REPO_ROOT` 解析到当前 clone（见脚本内 `MIMIR_REPO_ROOT` / `git rev-parse`） |

### 2.4 双 `gateway/run.py` 进程

| 步骤 | 操作 |
|------|------|
| **如何查** | `pgrep -af 'gateway/run.py'`；`pgrep -af 'cli.py gateway'`；可选：`cat "$MIMIR_AETHER_HOME/data/gateway.pid" 2>/dev/null` |
| **如何停** | 保留**一条**来自真源 clone 的进程；对其余 PID：`kill <pid>`，必要时 `kill -9`；避免同时从旧目录与新目录各启一份 |
| **验收** | `pgrep -af 'gateway/run.py' \| wc -l` 为 **1**（或你明确只跑 0/1 个实例）；存活进程的 cmdline 含 **`/src/MimirAether/gateway/run.py`**（或你的 `MIMIR_REPO_ROOT`），**不含** `.openclaw/projects/MimirAether` |

### 2.5 飞书凭证与启动路径

| 步骤 | 操作 |
|------|------|
| **如何查** | 仅查看键名（勿粘贴密钥）：`grep -E '^FEISHU_' "$MIMIR_AETHER_HOME/.env" 2>/dev/null`；确认**无** `~/.openclaw/projects/MimirAether/.env` 被 gateway 使用：`pgrep -af gateway` 进程的 cwd / 环境（`tr '\0' '\n' < /proc/<pid>/environ \| grep -E 'MIMIR_AETHER_HOME\|HERMES_HOME'`） |
| **如何停** | 在飞书开放平台**停用或轮换**旧 App；**仅**在 **`$MIMIR_AETHER_HOME/.env`** 保留新 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`（及所需 `FEISHU_*`）；删除或清空旧目录内 `.env` 的飞书键（先备份文件） |
| **验收** | 网关进程环境指向 **`MIMIR_AETHER_HOME`**；飞书后台仅**一个**在用应用；旧路径未再启动 gateway（结合 §2.1、§2.4） |

### 2.6 （建议）HTTP 健康与 CLI 健康

| 步骤 | 操作 |
|------|------|
| **如何查** | 端口以 `config.yaml` 为准，默认可试：`curl -sS --max-time 5 http://127.0.0.1:18999/health`；在 clone 根：`python3 cli.py gateway health` |
| **如何停** | 不适用（仅验收项） |
| **验收** | HTTP 返回 200 / `status` 正常；与 [`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) §3、[`gateway-cli-health.md`](./gateway-cli-health.md) 一致 |

---

## 3. 建议保留 / 归档（不强制删除）

| 对象 | 建议 |
|------|------|
| **`~/.openclaw/projects/MimirAether`** | **只读归档**或打 zip 冷备；勿作日常 `cd` 与启动目录；详见 [`MIMIR_OPENCLAW_BOUNDARY.md`](./MIMIR_OPENCLAW_BOUNDARY.md) §2.5 |
| **`~/.openclaw/` 其它技能/平台树** | 与 MA **无耦合**时可保留；勿把其中路径写入 MA 的 `MIMIR_AETHER_HOME` 或 cron |
| **`$MIMIR_AETHER_HOME` 旧数据** | **保留**为生产真源；删目录前整包备份 |
| **`{repo}/mimicore/public/*.md`** | 历史胶囊 **只读归档**；新胶囊真源为 **`$MIMIR_AETHER_HOME/memory/capsules/*.html`**（见 T02） |
| **第二套 mimicore 栈** | **禁止**启动 `mimicore/gateway`、`mimicore/cli`（见 [`MIMIR_MIMICORE_SPRING_SCOPE.md`](./MIMIR_MIMICORE_SPRING_SCOPE.md)） |

本清单**不要求**立即删除任何目录；目标是**无自动复活、无双实例、凭证单一**。

---

## 4. 总体验收（下线完成判据）

负责人在本机确认以下**全部**成立：

| # | 条件 |
|---|------|
| 1 | **仅一个** MA `gateway/run.py`（或明确停服为 0），且来自 **`MIMIR_REPO_ROOT`**，非 `~/.openclaw/projects/MimirAether` |
| 2 | **`openclaw-gateway.service`**（若曾安装）已 stop + disable，或不存在 |
| 3 | **cron / watchdog** 不引用旧 clone 路径 |
| 4 | **`curl` / `cli.py gateway health`** 对当前实例 OK（若应在线） |
| 5 | **飞书**：仅新 App 凭证在 **`$MIMIR_AETHER_HOME/.env`**；旧路径 gateway 未运行 |
| 6 | 记忆真源认知正确：可积累知识在 **`$MIMIR_AETHER_HOME/memory/`**（HTML），非 OpenClaw / 旧 `public/*.md` 新写入 |

---

## 5. 相关文档

| 文档 | 用途 |
|------|------|
| [`MIMIR_OPENCLAW_BOUNDARY.md`](./MIMIR_OPENCLAW_BOUNDARY.md) | T03 — OpenClaw / weavevault 零部署、禁止清单 |
| [`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md) | T02 — `memory/` HTML 真源 |
| [`path-contract.md`](./path-contract.md) | 仓库根 vs 数据根、历史路径豁免 |
| [`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) | 启动、日志、systemd/cron 注意 |
| [`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md) | `MIMIR_REPO_ROOT` / `MIMIR_AETHER_HOME` 示例 |
| [`SECURITY.md`](./SECURITY.md) | `.env` 与密钥边界 |
| [`GATEWAY_SYSTEMD_ENV.md`](./GATEWAY_SYSTEMD_ENV.md) | systemd `EnvironmentFile=` 迁移 |

---

## 附录：负责人可立即执行的一条

若时间只够做一件事：**运行 `pgrep -af 'gateway/run.py'`**，确认仅一条来自 `~/src/MimirAether`（或你的 clone 根），并对任何来自 `~/.openclaw/projects/MimirAether` 的进程执行 `kill`，再 `curl` 或 `python3 cli.py gateway health` 验证存活实例。
