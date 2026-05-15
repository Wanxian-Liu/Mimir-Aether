# MimirAether — Security overview (self-hosted)

本文描述**默认行为、配置含义与仓库内相关机制**，不是渗透测试报告。自托管离开 OpenClaw 平台后，**边界安全、密钥管理、TLS、反向代理、系统补丁与审计**由**部署方**负责；请结合你方威胁模型使用。

---

## 1. 威胁模型与责任边界

| 区域 | 说明 |
|------|------|
| **本仓库** | 说明默认绑定、API 密钥策略、技能安装扫描（`tools/skills_guard.py`）与 CLI 侧安装流程（`mimir_cli/skills_hub.py`）等**设计意图**。 |
| **你的环境** | 网络分区、防火墙、WAF、身份与访问控制、日志留存、备份与恢复、依赖漏洞响应 — **须自行落实**。 |

---

## 2. `api_server`（OpenAI 兼容 HTTP）

实现见 [`gateway/platforms/api_server.py`](../gateway/platforms/api_server.py)（`Platform.API_SERVER`）。

| 主题 | 行为摘要 |
|------|----------|
| **默认 host** | **`127.0.0.1`**（`DEFAULT_HOST`；可通过 `API_SERVER_HOST` / `platforms.api_server.extra.host` 覆盖）。 |
| **绑定到非 loopback** | 若 `is_network_accessible(host)` 为真且**未**配置可用 **`API_SERVER_KEY`**（或 `platforms.api_server.extra.key`），进程**拒绝启动**；若配置了过短/占位 key，亦会拒绝（使用 `has_usable_secret(..., min_length=8)`）。须使用强随机密钥（例如 `openssl rand -hex 32`）。 |
| **仅 loopback 且未配置 key** | **允许启动**，但请求**不鉴权** — 任意本机进程可访问会话、补全、cron 等相关 HTTP 面；多用户主机、容器共宿主、或经反代暴露时，**必须**设 key 或网络隔离。 |
| **健康检查与端口** | 与网关整体 `/health`、CLI 行为一致处见 [`gateway-cli-health.md`](./gateway-cli-health.md)（具体端口以你方 `config.yaml` / 环境为准，本文不固定端口号）。 |

---

## 3. 其它监听适配器（原则）

部分 webhook、短信、企业微信等入站适配器在默认或示例配置下可能监听 **`0.0.0.0`**（以各 `gateway/platforms/*.py` 与配置为准）。**不要**在未加 TLS 与访问控制的情况下将此类端口直接暴露公网；应在边缘做 **TLS 终止 + ACL/反代**，并定期审查绑定地址与防火墙规则。

---

## 4. 技能安装（`mimir skills install`）

| 步骤 | 说明 |
|------|------|
| **拉取与隔离** | Bundle 进入 quarantine 路径（由 hub 实现解析；见 `mimir_cli/skills_hub.py` 中 `quarantine_bundle` 等）。 |
| **静态扫描** | **`tools/skills_guard.scan_skill`**：基于 `THREAT_PATTERNS` 与 `INSTALL_POLICY`（同文件内 `trusted_repos` / `community` 等信任分级）。 |
| **策略** | `builtin` / `trusted` / `community` / `agent-created` 对 `safe` / `caution` / `dangerous` 的放行规则见 `INSTALL_POLICY`；**`community`** 在存在 findings 时默认 **block**，除非 CLI **`--force`**。 |
| **`--force`** | **仅应在人工审批后使用**；会绕过社区源的阻断策略，恶意技能可窃取本机与运行时文件。 |
| **GitHub 与审计** | 未认证 GitHub API 速率受限；建议在 **`$MIMIR_AETHER_HOME/.env`** 配置 **`GITHUB_TOKEN`** 或使用 `gh auth login`（提示见 `mimir_cli/skills_hub.py` 安装路径与 [`mimir_cli/tips.py`](../mimir_cli/tips.py)）。安装阻断/审计由 hub 侧 `append_audit_log` 等写入（实现位于 **`tools.skills_hub`** 与数据根下 `skills/.hub/` 树；以运行时 `get_mimir_home()` 为准）。 |

---

## 5. 密钥与配置面

- **主路径**：**`$MIMIR_AETHER_HOME/.env`** 与 **`$MIMIR_AETHER_HOME/config.yaml`**（及平台合并规则）；勿将含密钥文件提交进 git。  
- **契约与激活**：[`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md)、[`MIMIR_ACTIVATE.md`](./MIMIR_ACTIVATE.md)、[`path-contract.md`](./path-contract.md)。  
- **网关运维（启动、日志，无密钥）**：[`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md)。

---

## 6. 与 OpenClaw 脱钩（一句）

运行时**不再依赖** `~/.openclaw/config.yaml` 作为默认真源；遗留 **`OPENCLAW_*`** 环境变量含义见 [`OPENCLAW_ENV_LEGACY.md`](./OPENCLAW_ENV_LEGACY.md)。

---

## 相关链接

| 文档 / 代码 | 用途 |
|-------------|------|
| [`gateway-cli-health.md`](./gateway-cli-health.md) | `/health`、CLI 健康检查 |
| [`GATEWAY_SYSTEMD_ENV.md`](./GATEWAY_SYSTEMD_ENV.md) | systemd / `.env` 对齐 |
| [`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) | 运维清单（链回本文） |
| [`tools/skills_guard.py`](../tools/skills_guard.py) | 技能威胁模式与 `INSTALL_POLICY` |
| [`mimir_cli/skills_hub.py`](../mimir_cli/skills_hub.py) | `mimir skills` 安装与提示 |
