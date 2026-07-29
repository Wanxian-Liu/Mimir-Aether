---
description: Hermes工具系统研究与集成 - 学习Hermes模块化工具注册与分发机制，用于MimirAether工具系统设计参考
---

# MimirAether Tools System - Hermes工具系统研究与集成

## 研究日期：Phase 1 Day 4

---

## 一、Hermes工具系统架构概述

Hermes的工具系统是一个模块化、可扩展的工具注册与分发机制，核心由三个层次组成：

```
┌─────────────────────────────────────────────────────────────┐
│                    Toolset Layer (toolsets.py)              │
│  TOOLSETS字典 - 工具集分组，包含tools和includes字段         │
│  支持工具集组合（composition）和别名解析                     │
├─────────────────────────────────────────────────────────────┤
│                 Registry Layer (tools/registry.py)           │
│  ToolRegistry单例 - 工具元数据注册表                         │
│  管理schema、handler、check_fn、emoji等                       │
├─────────────────────────────────────────────────────────────┤
│                   Tool Layer (tools/*.py)                   │
│  各个工具模块 - web_tools.py, file_tools.py等                │
│  模块级调用registry.register()完成注册                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心组件详解

### 2.1 Toolset注册表 (toolsets.py)

**文件位置**: `~/.openclaw/projects/hermes-agent/toolsets.py`

**核心数据结构**:
```python
TOOLSETS = {
    "toolset_name": {
        "description": "工具集描述",
        "tools": ["tool1", "tool2"],      # 直接包含的工具
        "includes": ["other_toolset"]      # 包含其他工具集
    }
}
```

**关键函数**:
- `resolve_toolset(name)`: 递归解析工具集，返回所有工具名列表
- `resolve_multiple_toolsets(names)`: 合并多个工具集
- `get_toolset(name)`: 获取工具集定义
- `get_all_toolsets()`: 获取所有工具集名

**特殊别名**:
- `"all"` 或 `"*"`: 解析为所有工具

**示例 - Hermes CLI工具集**:
```python
_HERMES_CORE_TOOLS = [
    "web_search", "web_extract", "terminal", "process",
    "read_file", "write_file", "patch", "search_files",
    "vision_analyze", "image_generate",
    "skills_list", "skill_view", "skill_manage",
    "browser_navigate", "browser_snapshot", "browser_click",
    "text_to_speech", "todo", "memory", "session_search",
    "clarify", "execute_code", "delegate_task", "cronjob",
    "send_message", "ha_list_entities", "ha_get_state",
]

"hermes-cli": {
    "description": "Full interactive CLI toolset",
    "tools": _HERMES_CORE_TOOLS,
    "includes": []
}
```

---

### 2.2 Tool Registry (tools/registry.py)

**文件位置**: `~/.openclaw/projects/hermes-agent/tools/registry.py`

**ToolEntry元数据结构**:
```python
class ToolEntry:
    __slots__ = (
        "name",           # 工具名
        "toolset",        # 所属工具集
        "schema",         # OpenAI格式schema
        "handler",        # 处理函数
        "check_fn",       # 可用性检查函数
        "requires_env",   # 所需环境变量
        "is_async",       # 是否异步
        "description",    # 描述
        "emoji",          # 图标
        "max_result_size_chars"  # 最大结果大小
    )
```

**ToolRegistry核心方法**:
| 方法 | 功能 |
|------|------|
| `register(...)` | 注册工具 |
| `deregister(name)` | 注销工具 |
| `get_definitions(names)` | 获取工具schema（过滤不可用） |
| `dispatch(name, args)` | 执行工具 |
| `get_all_tool_names()` | 获取所有工具名 |
| `get_schema(name)` | 获取原始schema |
| `is_toolset_available(ts)` | 检查工具集可用性 |

**注册函数签名**:
```python
registry.register(
    name="tool_name",           # 工具名称
    toolset="toolset_name",      # 所属工具集
    schema={...},                # OpenAI格式schema
    handler=func,                # 处理函数
    check_fn=availability_check, # 可用性检查（可选）
    requires_env=["API_KEY"],   # 所需环境变量（可选）
    is_async=False,             # 是否异步（可选）
    description="...",          # 描述（可选）
    emoji="🔧"                  # 图标（可选）
)
```

---

### 2.3 工具模块注册模式

**文件位置**: `~/.openclaw/projects/hermes-agent/tools/*.py`

**标准注册流程**:

1. 定义schema（OpenAI格式）:
```python
TOOL_SCHEMA = {
    "name": "tool_name",
    "description": "工具描述",
    "parameters": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```

2. 定义处理函数:
```python
def handle_tool(args, **kwargs):
    # 处理逻辑
    return tool_result(data)
    # 或返回 tool_error(message)
```

3. 模块级注册:
```python
from tools.registry import registry, tool_error

registry.register(
    name="tool_name",
    toolset="my_toolset",
    schema=TOOL_SCHEMA,
    handler=handle_tool,
    check_fn=check_requirements,
    emoji="🛠️"
)
```

---

## 三、工具配置系统 (tools_config.py)

**文件位置**: `~/.openclaw/projects/hermes-agent/hermes_cli/tools_config.py`

### 3.1 可配置工具集

```python
CONFIGURABLE_TOOLSETS = [
    ("web",             "🔍 Web Search & Scraping",    "web_search, web_extract"),
    ("browser",         "🌐 Browser Automation",       "navigate, click, type..."),
    ("terminal",        "💻 Terminal & Processes",      "terminal, process"),
    ("file",            "📁 File Operations",           "read, write, patch, search"),
    ("code_execution",  "⚡ Code Execution",            "execute_code"),
    ("vision",          "👁️  Vision / Image Analysis",  "vision_analyze"),
    ("image_gen",       "🎨 Image Generation",          "image_generate"),
    ("skills",          "📚 Skills",                    "list, view, manage"),
    ("todo",            "📋 Task Planning",             "todo"),
    ("memory",          "💾 Memory",                    "persistent memory..."),
    # ... 更多
]
```

### 3.2 提供商感知配置

```python
TOOL_CATEGORIES = {
    "tts": {
        "name": "Text-to-Speech",
        "providers": [
            {"name": "Nous Subscription", ...},
            {"name": "Microsoft Edge TTS", ...},
            {"name": "OpenAI TTS", ...},
            {"name": "ElevenLabs", ...},
        ]
    },
    "web": {
        "providers": [
            {"name": "Nous Subscription", ...},
            {"name": "Firecrawl Cloud", ...},
            {"name": "Exa", ...},
            {"name": "Tavily", ...},
        ]
    }
}
```

### 3.3 平台工具集映射

```python
PLATFORMS = {
    "cli": {"label": "CLI", "default_toolset": "hermes-cli"},
    "telegram": {"label": "Telegram", "default_toolset": "hermes-telegram"},
    "discord": {"label": "Discord", "default_toolset": "hermes-discord"},
    # ... 更多平台
}
```

---

## 四、MCP集成

Hermes支持MCP（Model Context Protocol）服务器作为工具源：

- 动态发现MCP服务器
- 工具自动注册到registry
- 支持`notifications/tools/list_changed`事件处理

---

## 五、MimirAether集成要点

### 5.1 工具发现

```python
# 导入工具模块（触发注册）
import tools.web_tools
from tools import browser_tool

# 获取所有注册的工具
from tools.registry import registry
all_tools = registry.get_all_tool_names()
```

### 5.2 工具执行

```python
from tools.registry import registry

# 获取可用工具定义
schemas = registry.get_definitions({"web_search", "terminal"})

# 执行工具
result = registry.dispatch("web_search", {"query": "test"})
```

### 5.3 工具集解析

```python
from toolsets import resolve_toolset, resolve_multiple_toolsets

# 解析单个工具集
tools = resolve_toolset("file")  # ["read_file", "write_file", ...]

# 解析多个工具集
all_tools = resolve_multiple_toolsets(["web", "file", "terminal"])
```

### 5.4 检查工具可用性

```python
from tools.registry import registry

# 检查工具集
available = registry.is_toolset_available("web")

# 获取工具集状态
available_toolsets, unavailable = registry.check_tool_availability()
```

---

## 六、创建新工具的步骤

1. **创建工具文件**: `tools/my_tool.py`
2. **定义schema**: OpenAI格式参数定义
3. **实现handler**: 处理函数，返回JSON字符串
4. **模块级注册**: `registry.register(...)`
5. **更新toolsets.py**: 添加到相应工具集
6. **（可选）更新tools_config.py**: 添加到CONFIGURABLE_TOOLSETS

---

## 七、参考文件路径

| 文件 | 路径 |
|------|------|
| 工具集定义 | `~/.openclaw/projects/hermes-agent/toolsets.py` |
| 注册表 | `~/.openclaw/projects/hermes-agent/tools/registry.py` |
| 工具配置 | `~/.openclaw/projects/hermes-agent/hermes_cli/tools_config.py` |
| 示例工具 | `~/.openclaw/projects/hermes-agent/tools/delegate_tool.py` |
|             | `~/.openclaw/projects/hermes-agent/tools/web_tools.py` |

---

## 八、关键设计模式

### 8.1 单例模式
```python
registry = ToolRegistry()  # 模块级单例
```

### 8.2 检查函数模式
```python
def check_delegate_requirements() -> bool:
    """工具可用性检查，返回True表示可用"""
    return True
```

### 8.3 结果格式化
```python
from tools.registry import tool_error, tool_result

return tool_error("错误信息")
return tool_result({"key": "value"})
```

### 8.4 平台感知
```python
# 根据平台启用不同工具集
platform_toolsets = _get_platform_tools(config, "cli")
```
