# PI-L03: TUI / 子 Agent 与 Mimir CLI 边界 — MimirAether 对照

> 只读学习，不复制 TS 文件、不修改 Mimir 代码。

## 源

- pi-agent: `packages/coding-agent/README.md` (655行), `src/cli.ts`, `src/main.ts` (773行), `src/modes/` (interactive/print/rpc)
- MimirAether: `cli.py` (14行, entry shim → `mimir_cli.main`)

## pi 的 4 种运行模式

| 模式 | 入口 | 特征 |
|------|------|------|
| **Interactive (TUI)** | `InteractiveMode` | 全屏终端 UI：编辑器、消息列表、Footer、Command palette (`/`)、快捷键、扩展 |
| **Print** | `runPrintMode` | 单次 prompt → 打印结果 → 退出，适合 pipeline 集成 |
| **RPC** | `runRpcMode` | JSON-RPC over stdio，供宿主进程嵌入 (`openclaw` SDK) |
| **JSON** | `--json` | 类似 Print，结构化 JSON 输出 |

## 5 条异同

### 相同

1. **Agent 核心一致**：两方的 agent loop 共享「提示 → LLM → tool → 继续」的迭代模式，区别在 shell 集成层。
2. **Session 持久化**：pi 的 JSONL 会话文件 (`~/.pi/agent/sessions/`) 与 Mimir 的 JSONL (`trajectories/YYYY-MM-DD/<session_id>.jsonl`) 结构相似——都按时间组织、可继续上次会话。
3. **`/new` 重置**：pi 和 Mimir 都支持 `/new` 指令重置会话上下文，且 persistent.json 跨会话保留。
4. **多 provider 支持**：pi 支持 30+ provider/API 密钥，Mimir 支持 DeepSeek/OpenRouter/Anthropic。两方都有 provider 抽象层。

### 不同

1. **TUI 有无**：pi 是**亲生的 TUI 应用**——全彩终端 UI，消息/文件实时渲染，扩展可替换编辑器。Mimir 是**纯聊天协议后端**——无自建终端 UI，通过 Feishu/Telegram/Discord 等平台暴露聊天界面。Mimir 的 CLI 端口 (`cli.py` → `mimir_cli.main`) 只是文本 I/O shim，无 TUI 框架。
2. **消息队列（steer/followUp）的 UI 层**：pi 的消息队列是用户可见的——按 Enter 排入 steering、Alt+Enter 排入 follow-up、Escape 撤回。Mimir 无此概念——所有用户消息即时生效。
3. **扩展生态**：pi 有完整的扩展系统（`ExtensionFactory`、钩子事件、自定义命令、自定义 UI 组件、输入变换）。Mimir 有 skill 扩展但无 UI 扩展——技能只影响 agent 行为，不影响聊天 UI。
4. **会话树/分支**：pi 支持 `/tree`（同文件分支切换）、`/fork`（创建新文件分支）、`/clone`（复制分支）。Mimir 的 session ID 是线性串，无分支概念。
5. **运行模式多样性**：pi 有 Interactive / Print / RPC / JSON 四种模式，RPC 模式允许宿主进程（如 OpenClaw SDK）直接嵌入 agent。Mimir 的门户是 Gateway（WebSocket/HTTP 多平台），RPC 等价物是 Gateway 的 `api_server.py`。

## 可借鉴（Mimir 落点）

1. **Print 模式的单次 prompt CLI**：Mimir CLI 目前只做交互式 shim。加一个 `--one-shot "prompt"` 模式可方便 script/CI 调用，输出纯文本结果。
2. **会话恢复选择器**：pi 的 `-r` 浏览历史会话 + `-c` 继续最近会话——Mimir CLI 可加类似 `--resume` flag。
3. **AGENTS.md 上下文注入**：pi 从 `~/.pi/agent/` + 父目录遍历加载。Mimir 的 `prompt_builder` 已有类似但路径不同（`prompt_library.json`/skills）。

## 明确不做

1. **TUI 框架实现**：Mimir 作为聊天后端，UI 层由飞书/Telegram/Discord 等平台承载。自建 TUI 超出范围。
2. **扩展系统**：pi 的扩展模型（替换编辑器、自定义命令）绑定于 TUI 架构，不可移植。
3. **会话树/分支**：Mimir session 的单向线性模型是生产稳定的简化设计，无分支需求。
