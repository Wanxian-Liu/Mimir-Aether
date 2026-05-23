# EV-P04 — GOD 文件清单（2026-05-24）

> **扫描**：`find` + `wc -l`，≥1500 降序（排除 `.git`/`node_modules`/`.venv`）；`mimicore/` 无 ≥1500；`cli.py` **14** 行已退出（[dead-code-audit](./dead-code-audit.md)）。

## 摘要

- **24** 文件 / **57,477** 行（2026-05-21：25 / 57,764；`cli.py` 退出榜单）。
- **P0×2** `mimir_cli/main.py`、`gateway/router_mixin.py` · **P1×9** CLI/Gateway 配置与桥接 · **P2×13** 工具/平台/迁移/离线。

## TOP24（≥1500 行）

| # | 文件 | 行数 | 职责 | 优先级 |
|---|------|------|------|:--:|
| 1 | `mimir_cli/main.py` | 6032 | CLI 主入口（argparse、子命令编排） | 🔴 P0 |
| 2 | `gateway/router_mixin.py` | 3573 | Gateway 消息路由 | 🔴 P0 |
| 3 | `mimir_cli/config.py` | 3324 | CLI 配置读写/合并 | 🟡 P1 |
| 4 | `mimir_cli/setup.py` | 3139 | CLI 安装/初始化 | 🟡 P1 |
| 5 | `mimir_cli/gateway.py` | 3047 | CLI→Gateway 客户端 | 🟡 P1 |
| 6 | `optional-skills/.../openclaw_to_hermes.py` | 2816 | OpenClaw→Hermes 迁移脚本 | 🟢 P2 |
| 7 | `agent/auxiliary_client.py` | 2580 | 辅助/多模型客户端 | 🟢 P2 |
| 8 | `tools/browser_tool.py` | 2460 | 浏览器自动化工具 | 🟢 P2 |
| 9 | `tools/mcp_tool.py` | 2266 | MCP 工具集成 | 🟢 P2 |
| 10 | `agent/credential_pool.py` | 2215 | 凭证池 | 🟢 P2 |
| 11 | `gateway/command_handlers.py` | 2116 | Gateway 命令处理 | 🟡 P1 |
| 12 | `tools/web_tools.py` | 2114 | Web 搜索/提取 | 🟢 P2 |
| 13 | `gateway/platforms/base.py` | 2072 | 平台适配基类 | 🟢 P2 |
| 14 | `gateway/platforms/matrix.py` | 2005 | Matrix 平台 | 🟢 P2 |
| 15 | `mimir_cli/web_server.py` | 1992 | CLI Web 服务 | 🟡 P1 |
| 16 | `mimir_cli/models.py` | 1966 | CLI 数据模型 | 🟡 P1 |
| 17 | `gateway/platforms/api_server.py` | 1917 | HTTP API 服务 | 🟢 P2 |
| 18 | `gateway/platforms/weixin.py` | 1829 | 微信平台 | 🟢 P2 |
| 19 | `gateway/agent_mixin.py` | 1819 | Gateway↔Agent 桥接 | 🟡 P1 |
| 20 | `tools/terminal_tool.py` | 1751 | 终端/shell 工具 | 🟢 P2 |
| 21 | `mimir_cli/tools_config.py` | 1698 | CLI 工具配置 | 🟡 P1 |
| 22 | `gateway/platforms/slack.py` | 1670 | Slack 平台 | 🟢 P2 |
| 23 | `agent/prompt_builder.py` | 1569 | 系统/工具 Prompt 构建 | 🟢 P2 |
| 24 | `trajectory_compressor.py` | 1507 | 轨迹压缩（离线） | 🟡 P1 |

**vs 2026-05-21**：`cli.py` 退出；余文件行数多数 ±20；无新 ≥1500 候选（1490–1499 空）。**Phase 1**：先拆 P0 `main`/`router_mixin`；P2 工具抽 handler，对齐 `tools.registry`。
