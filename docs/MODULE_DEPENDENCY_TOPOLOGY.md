# MimirAether 模块依赖拓扑

> **生成**: 2026-05-21 | MimirAether 自审计  
> **方法**: grep 全仓库 `from agent.|from gateway.|from tools.|from mimicore.`  
> **规则**: 只记录跨模块引用（模块内部自引用不计）

---

## 1. 四层依赖总览

```
┌─────────────────────────────────────┐
│              gateway/               │
│   run.py · router_mixin(3568行)     │
│   agent_mixin · command_handlers    │
│   cron_mixin · session_mixin        │
│        ↙↓↓ 强依赖 (40+处)            │
│  ┌──────────────────────────────┐   │
│  │          agent/              │   │
│  │  core_loop · agent_loop      │   │
│  │  auxiliary_client(1521行)    │   │
│  │  exec_mixin · recovery_mixin │   │
│  │  skill_utils · skill_funcs   │   │
│  │  display · redact · insights │   │
│  │      ↕ 双向 (各20+处)         │   │
│  │  ┌────────────────────────┐  │   │
│  │  │        tools/          │  │   │
│  │  │  strategy · registry   │  │   │
│  │  │  skill_manager_tool    │  │   │
│  │  │  web_tools · vision    │  │   │
│  │  │  browser_tool · mcp    │  │   │
│  │  └────────────────────────┘  │   │
│  │      ↓ 弱依赖 (间接)         │   │
│  │  ┌────────────────────────┐  │   │
│  │  │   tools/mimircore_tool │  │   │
│  │  │        ↓ 调用           │  │   │
│  │  │      mimicore/         │  │   │
│  │  │  (45K行·知识工厂)       │  │   │
│  │  └────────────────────────┘  │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘

外部（离线脚本）: cli.py · api_service.py · scripts/ · acp_adapter/
    ↓ 直接引用 mimicore
```

| 关系 | 引用数 | 方向 | 风险 |
|------|:--:|------|:--:|
| **gateway → agent** | ~40+ | 单向 | 🟡 gateway 不是独立层 |
| **agent → gateway** | **0** | 无 | ✅ 依赖单向正确 |
| **agent ↔ tools** | ~20+ / ~20+ | **双向** | 🔴 耦合最严重 |
| **gateway → tools** | ~20 | 单向 | 🟡 gateway 直接调 tools 绕过 agent |
| **tools → mimicore** | 1 处 | 间接 | 🟢 仅 mimircore_tool.py |
| **gateway → mimicore** | 0 | 无 | ✅ |
| **离线脚本 → mimicore** | ~15 | 单向 | 🟢 符合预期 |

---

## 2. gateway → agent（40+ 处·强依赖）

gateway 层严重依赖 agent 的内部模块：

| gateway 文件 | 引用的 agent 模块 | 用途 |
|-------------|-------------------|------|
| `agent_mixin.py` | `display` (set_tool_preview / get_tool_emoji) | UI 渲染 |
| `agent_mixin.py` | `title_generator` (maybe_auto_title) | 自动标题 |
| `health_mixin.py` | `smart_model_routing` (resolve_turn_route) | 模型路由 |
| `session_mixin.py` | `smart_model_routing` (resolve_turn_route) | 同上 |
| `cron_mixin.py` | `prompt_builder` (PLATFORM_HINTS) | 系统提示 |
| `cron_mixin.py` | `skill_commands` (_build_skill_message) | 技能加载 |
| `cron_mixin.py` | `redact` (RedactingFormatter) | 日志脱敏 |
| `command_handlers.py` | `skill_commands` / `model_metadata` / `insights` / `manual_compression_feedback` / `rate_limit_tracker` / `usage_pricing` | 命令处理 |
| `router_mixin.py` | `skill_commands` / `model_metadata` / `insights` / `context_references` / `manual_compression_feedback` / `rate_limit_tracker` / `usage_pricing` / `skill_utils` | 消息路由 |
| `run.py` | `redact` (RedactingFormatter) | 日志 |
| `_shared.py` | `skill_utils` (get_all_skills_dirs) | 技能目录 |
| `platforms/webhook.py` | `skill_commands` | Webhook |
| `platforms/api_server.py` | `display` | API |

**判断**: gateway 不是一个独立的"平台层"——它直接读取 agent 内部的 display/skill/insights 模块作为工具函数使用。如果 agenda 要拆分 gateway 或 agent，必须同时处理这些跨层引用。

---

## 3. agent ↔ tools（双向耦合·最严重）

### 3.1 agent → tools

| agent 文件 | 引用的 tools 模块 |
|-----------|-------------------|
| `callers_mixin.py` | `toolsets` (resolve_enabled_tools) |
| `display.py` | `registry` / `skill_manager_tool` |
| `exec_mixin.py` | `strategy` (route_tool_call / pre_validate_tool_call) |
| `agent_loop.py` | `tool_result_storage` / `terminal_tool` |
| `core_loop.py` | `toolsets` (resolve_enabled_tools) |

### 3.2 tools → agent

| tools 文件 | 引用的 agent 模块 |
|-----------|-------------------|
| `web_tools.py` | `auxiliary_client` · `redact` |
| `file_tools.py` | `redact` |
| `vision_tools.py` | `auxiliary_client` |
| `send_message_tool.py` | `redact` |
| `browser_camofox.py` | `redact` · `auxiliary_client` |
| `browser_tool.py` | `auxiliary_client` · `redact` |
| `terminal_tool.py` | `redact` |
| `delegate_tool.py` | `display` · `credential_pool` |
| `skill_manager_tool.py` | `skill_utils` · `skill_funcs` · `prompt_builder` |
| `strategy.py` | `tool_guard` |
| `code_execution_tool.py` | `redact` |
| `mcp_tool.py` | `auxiliary_client` |
| `openrouter_client.py` | `auxiliary_client` |

**判断**: `redact` 被 8 个工具文件引用——它是 agent 和 tools 之间最强的耦合点。`auxiliary_client` 被 5 个工具文件引用——tools 直接调用 LLM，不经过 agent_loop。**拆分 agent/tools 的边界必须先解决 redact + auxiliary_client 的归属。**

---

## 4. Mimicore 引用分析

### 4.1 在线引用（影响运行时）

| 文件 | 引用 | 阻塞性 |
|------|------|:--:|
| `tools/mimircore_tool.py` | `CapsuleGenerator` / `CapsuleType` | 🟢 工具调用时才加载 |
| `skills/.../mimiraether-self_evolution/__init__.py` | `ThreeRingClosedLoop` | 🟢 技能加载时 |
| `activate_self_evolution.py` | `ThreeRingClosedLoop` / `SelfDriveEngine` | 🟢 独立激活脚本 |
| `acp_adapter/session.py` | `load_config` | 🟡 会话管理 |

### 4.2 离线引用（不影响运行时）

| 文件 | 引用 |
|------|------|
| `cli.py` | config.model_defaults |
| `api_service.py` | config.model_defaults |
| `scripts/` (5 个脚本) | CapsuleGenerator |
| `run_capsule_*.py` (4 个) | CapsuleGenerator |

**判断**: Mimicore 在 Mimir 运行时仅通过 `mimircore_tool.py` 间接调用，不在热路径上。**服务化的紧迫性低**——它不是当前耦合问题的根源。

---

## 5. 依赖关系矩阵

| ↓ 引用者 / 被引用者 → | agent | gateway | tools | mimicore |
|------------------------|:-----:|:-------:|:-----:|:--------:|
| **agent** | — | **0** ✅ | ~20 🔴 | 0 (间接) |
| **gateway** | ~40 🔴 | — | ~20 🟡 | 0 ✅ |
| **tools** | ~20 🔴 | 0 ✅ | — | 1 🟢 |
| **离线脚本** | 0 | 0 | 0 | ~15 🟢 |

---

## 6. 循环依赖检测

| 检查 | 结果 |
|------|:--:|
| agent → gateway → agent | ✅ 无（agent 不引用 gateway） |
| agent → tools → agent | 🔴 **存在**（agent→display→registry 与 tools→agent→redact 形成双向） |
| gateway → tools → agent → gateway | ✅ 无 |
| agent → mimicore → agent | ✅ 无 |
| 三方环 | ✅ 无 |

---

## 7. 依赖强度 TOP15

### 被依赖最多的模块（高拆风险）

| 排名 | 模块 | 被引用次数 | 引用者 |
|:--:|------|:--:|------|
| 1 | `agent.redact` | **8** | tools(6) + gateway(2) |
| 2 | `agent.auxiliary_client` | **6** | tools(5) + agent(1) |
| 3 | `agent.skill_commands` | **6** | gateway(5) + agent(1) |
| 4 | `agent.model_metadata` | **5** | gateway(5) |
| 5 | `agent.display` | **4** | gateway(3) + tools(1) |
| 6 | `agent.skill_utils` | **4** | gateway(2) + tools(2) |
| 7 | `tools.process_registry` | **4** | gateway(4) |
| 8 | `agent.insights` | **3** | gateway(3) |
| 9 | `agent.manual_compression_feedback` | **3** | gateway(3) |
| 10 | `agent.rate_limit_tracker` | **2** | gateway(2) |
| 11 | `agent.usage_pricing` | **2** | gateway(2) |
| 12 | `agent.smart_model_routing` | **2** | gateway(2) |
| 13 | `agent.prompt_builder` | **2** | gateway(1) + tools(1) |
| 14 | `agent.skill_curator` | **2** | agent(2)（内部引用） |
| 15 | `agent.credential_pool` | **2** | tools(1) + agent(1) |

---

## 8. 关键结论

### 🔴 根因耦合点
**`agent.redact`** 是最强的跨层耦合点——被 8 个文件引用（6 个 tools + 2 个 gateway）。如果在 tools 层做同样的脱敏逻辑，会产生重复代码。如果提取到独立层，需要同时改 8 个调用方。

### 🟡 架构假象
gateway 虽然叫"网关"，但它不是独立层——它对 agent 有 40+ 处直接引用。router_mixin（3568 行）和 command_handlers 是最大的违规者。

### 🟢 好消息
- **没有三方环**（agent→gateway→tools→agent 不存在）
- **Mimicore 不是问题根源**——它只在 1 个工具中在线调用
- **agent → gateway 单向 = 0**——依赖方向正确，agent 不依赖 gateway

### 📐 拆分次序建议

| 步 | 做什么 | 影响面 |
|----|--------|--------|
| 1 | **提取 `redact` 到 `shared/`** | 改 8 个调用方 |
| 2 | **提取 `auxiliary_client` 的 LLM 调用到 `shared/`** | 改 5 个 tools 调用方 |
| 3 | **拆分 gateway ↔ agent 交叉引用** | 最大工程（40+ 处） |
| 4 | **打破 agent ↔ tools 双向耦合** | 引入接口层 |

---

## 9. 与三方案的对齐

| 方案 | 对齐度 | 说明 |
|------|:--:|------|
| **工程方案** | ⬆️ 高 | GOD 拆分（router_mixin 3568 行 / command_handlers）依赖本拓扑确定边界 |
| **架构方案** | ⬆️ 高 | 方向一（Agent Core 重划）依赖 §8 的 redact/auxiliary 提取；方向二（Mimicore 服务化）经本拓扑证实**紧迫性低** |
| **智商方案** | 🟡 中 | 方向六（意图预测）不涉及跨层耦合，可独立推进；方向一（学习引擎）只改 agent 内部 |

---

> **技术债务已标注**: `redact` 耦合 8 处 / `auxiliary_client` 耦合 5 处 / gateway→agent 40+ 处 / agent↔tools 双向耦合。
>
> 本拓扑是只读审计产物，零代码改动。最终拆分顺序由 Cursor 根据 Bridge §3 的 C1-C6 + AC1-AC9 判断表决定。
