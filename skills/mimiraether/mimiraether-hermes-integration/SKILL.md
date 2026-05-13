---
name: "mimiraether-hermes-integration"
description: >
  MimirAether与Hermes Agent深度集成方案 — 实现工具共享、技能互通、子代理调度和协同工作流。支持通过Hermes工具生态扩展MimirAether能力。

version: "1.0.0"
category: "mimiraether"
tags:
  - hermes
  - integration
  - tools
  - skills
  - 协同
  - 集成
---
# mimiraether-hermes-integration

## name

MimirAether Hermes Integration — Hermes集成

## description

MimirAether与Hermes Agent的深度集成，实现工具共享、技能互通和协同工作流。支持通过Hermes的工具生态扩展MimirAether的能力。

## 核心功能列表

- **Hermes工具发现**：自动发现并注册Hermes可用的工具
- **子代理调度**：通过Hermes spawning autonomous agents执行复杂任务
- **技能共享**：MimirAether技能与Hermes技能系统互通
- **MCP集成**：通过Hermes的MCP client连接外部MCP服务器
- **工作流编排**：组合MimirAether和Hermes能力执行复杂任务
- **结果聚合**：收集和整合来自Hermes子代理的执行结果

## 架构

```
MimirAether (Knowledge Layer)
    │
    ├── skills/          ← 共享技能目录
    │   ├── mimiraether/  (MimirAether 原生技能)
    │   └── software-development/  (Hermes 派生技能)
    │
    ├── Hermes Bridge ──────────────┐
    │   ├── tools_proxy.py          │
    │   ├── subagent_dispatcher.py  │
    │   └── mcp_bridge.py           │
    │                                ▼
    └────────────────────── Hermes Agent (Execution Layer)
                             ├── tools/ (Hermes原生工具)
                             ├── platforms/ (多平台后端)
                             └── mcp/ (MCP协议客户端)
```

## 工具共享机制

### MimirAether → Hermes
MimirAether 使用 Hermes 工具生态时：
```python
# 通过 Hermes Bridge 调用 Hermes 工具
from hermes_bridge import call_hermes_tool

result = call_hermes_tool("delegate_task", goal="...", context="...")
```

### Hermes → MimirAether
Hermes 代理需要 MimirAether 知识时：
```python
# 查询 MimirAether 知识库
from hermes_bridge import query_mimir_knowledge

capsules = query_mimir_knowledge("async programming patterns", top_k=5)
```

## 子代理调度

### 何时使用子代理
- **长任务** (>5min): 异步委托，主会话不阻塞
- **独立任务**: 可并行执行，无数据依赖
- **专业化任务**: 需要特定技能或工具集
- **探索性任务**: 多种方案并行探索

### 调度模式

**模式1: Fire-and-Forget**
```python
delegate_task(goal="Run tier0 tests", context="cd ~/.openclaw/projects/MimirAether && ./run_ralph_tier0.sh")
```

**模式2: Two-Stage Review** (SDD)
```python
# Stage 1: Spec compliance
delegate_task(goal="Implement caching per spec", ...)
→ Review output against spec
# Stage 2: Code quality
delegate_task(goal="Review and fix code quality issues", ...)
```

**模式3: Parallel Fan-Out**
```python
# 同时派发多个独立任务
tasks = [
    delegate_task(goal="Optimize database queries"),
    delegate_task(goal="Refactor auth middleware"),
    delegate_task(goal="Add API rate limiting"),
]
results = gather(tasks)  # 等待全部完成
```

## 技能互通

### 技能发现
```bash
# 列出所有可用技能（含Hermes和MimirAether）
python scripts/list_all_skills.py --source both

# 按类别过滤
python scripts/list_all_skills.py --category software-development
```

### 技能转换
Hermes技能适配到MimirAether:
1. 路径转换: `.hermes/plans/` → `.mimir/plans/`
2. 工具名映射: `write_file` → `write_file` (兼容), `execute_command` → `terminal`
3. 引用更新: `systematic-debugging` → `mimiraether-root-cause-debugging`

## MCP集成

通过Hermes的MCP客户端连接外部工具服务器：

```python
# 配置MCP服务器
from hermes_bridge import register_mcp_server

register_mcp_server(
    name="github-tools",
    transport="stdio",
    command="npx",
    args=["@anthropic/mcp-github"],
)
```

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| Hermes工具不可用 | Bridge未初始化 | 重启会话 / 检查hermes_bridge进程 |
| 子代理超时 | 任务过重 | 拆分任务 / 增加超时时间 |
| 技能重复加载 | 两套技能系统冲突 | 使用唯一入口 `skill_view` |
| MCP连接失败 | 服务器未启动 | 检查MCP服务器状态 |
