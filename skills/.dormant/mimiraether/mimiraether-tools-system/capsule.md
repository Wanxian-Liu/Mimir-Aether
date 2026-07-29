# [DORMANT] mimiraether-tools-system

**沉寂时间**: 2026-07-29T08:53:25.052975+00:00
**原始分类**: mimiraether
**描述**: Hermes工具系统研究与集成 - 学习Hermes模块化工具注册与分发机制，用于MimirAether工具系统设计参考
**触发阈值**: 60天未触碰

---

## 技能要点

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
    "description": "Full interactive CL

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-tools-system")` 即可自动唤醒。
