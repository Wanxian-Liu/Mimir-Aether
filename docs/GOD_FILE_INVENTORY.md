# GOD 文件清单 + 废弃代码审计

**日期**：2026-05-21  
**来源**：EV-P03a + EV-P03b + EV-P04（琬弦工程方案第一期）

> **废弃代码真源（2026-05-24）**：以 [`docs/phase0/dead-code-audit.md`](./phase0/dead-code-audit.md) 为准；下文 EV-P03a/b 为历史快照，勿照抄。

---

## EV-P03a：tool_registry.py 引用确认

```
./agent/callers_mixin.py:16    import tools.registry as _tool_registry_module
./agent/config_mixin.py:20     import tools.registry as _tool_registry_module
./agent/exec_mixin.py:16       import tools.registry as _tool_registry_module
./agent/core_loop.py:180       import tools.registry as _tool_registry_module
./agent/core_loop.py:796       import tools.registry as _tool_registry_module
```

**判定**：🔴 **不可删除** — `tools/registry` 被 4 个 agent 模块 + 1 个延迟导入引用（共 5 处）。方案 §3.2 提议删除 tool_registry.py 需重新评估。

## EV-P03b：异常文件排查

方案中提到两个可疑模式：
- `{"content": "#!` — grep 全仓库无匹配
- `{"content": "\"\"\"\nTaskLoop` — grep 全仓库无匹配

**判定**：两个可疑模式在 MimirAether 仓库中不存在。可能是其他仓库或 OpenClaw 环境中的残留。

---

## EV-P04：GOD 文件清单（≥1500 行 · TOP25）

> **GOD 真源（2026-05-24）** → [`docs/phase0/god-file-inventory.md`](./phase0/god-file-inventory.md)（24 文件；`cli.py` 已退出）。下表为 2026-05-21 历史快照。

| # | 文件 | 行数 | 职责 | GOD 拆分优先级 |
|---|------|------|------|:--:|
| 1 | `mimir_cli/main.py` | 6052 | CLI 主入口（Mimir CLI） | 🔴 P0 |
| 2 | `cli.py` | 5836 | 旧 CLI 入口（D7 计划删除） | 🔴 P0 |
| 3 | `gateway/router_mixin.py` | 3568 | Gateway 消息路由 | 🔴 P0 |
| 4 | `mimir_cli/config.py` | 3312 | CLI 配置 | 🟡 P1 |
| 5 | `mimir_cli/setup.py` | 3139 | CLI 安装 | 🟡 P1 |
| 6 | `mimir_cli/gateway.py` | 3047 | CLI→Gateway 客户端 | 🟡 P1 |
| 7 | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py` | 2816 | OpenClaw→Hermes 迁移 | 🟢 P2 |
| 8 | `agent/auxiliary_client.py` | 2580 | 辅助客户端 | 🟢 P2 |
| 9 | `tools/browser_tool.py` | 2460 | 浏览器工具 | 🟢 P2 |
| 10 | `tools/mcp_tool.py` | 2266 | MCP 工具 | 🟢 P2 |
| 11 | `agent/credential_pool.py` | 2215 | 凭证池 | 🟢 P2 |
| 12 | `tools/web_tools.py` | 2114 | Web 搜索/提取工具 | 🟢 P2 |
| 13 | `gateway/command_handlers.py` | 2111 | Gateway 命令处理 | 🟡 P1 |
| 14 | `gateway/platforms/base.py` | 2072 | 平台基类 | 🟢 P2 |
| 15 | `gateway/platforms/matrix.py` | 2005 | Matrix 平台 | 🟢 P2 |
| 16 | `mimir_cli/web_server.py` | 1992 | CLI Web 服务器 | 🟡 P1 |
| 17 | `mimir_cli/models.py` | 1966 | CLI 数据模型 | 🟡 P1 |
| 18 | `gateway/platforms/api_server.py` | 1902 | API 服务器 | 🟢 P2 |
| 19 | `gateway/platforms/weixin.py` | 1829 | 微信平台 | 🟢 P2 |
| 20 | `gateway/agent_mixin.py` | 1819 | Gateway-Agent 桥接 | 🟡 P1 |
| 21 | `tools/terminal_tool.py` | 1751 | 终端工具 | 🟢 P2 |
| 22 | `mimir_cli/tools_config.py` | 1698 | CLI 工具配置 | 🟡 P1 |
| 23 | `gateway/platforms/slack.py` | 1670 | Slack 平台 | 🟢 P2 |
| 24 | `agent/prompt_builder.py` | 1560 | Prompt 构建器 | 🟢 P2 |
| 25 | `trajectory_compressor.py` | 1507 | 轨迹压缩器（离线） | 🟡 P1 |

**统计**：25 文件共 57,764 行。P0 优先级 3 个 / P1 优先级 7 个 / P2 优先级 15 个。

---

## 与琬弦方案的差异

| 方案假设 | 实际发现 |
|---------|---------|
| tool_registry.py 可删 | ❌ 5 处引用，不可删 |
| GOD 文件 ~25 个 ≥1500 行 | ✅ 确认 25 个 |
| 异常文件 `{"content": "#!` 存在 | ❌ 不存在 |
