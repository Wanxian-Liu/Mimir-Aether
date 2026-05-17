---
name: mimiraether-context-engine
description: 管理和优化MimirAether的对话上下文
version: 1.0.0
author: MimirAether
license: MIT
metadata:
  mimiraether:
    tags: [context, memory, session, optimization]
    related_skills: [mimiraether-memory-nudge, mimiraether-context-compressor]
---

# MimirAether Context Engine

## 概述

管理MimirAether的对话上下文，确保长对话中保持连贯性和效率。

**核心原则：** 上下文是有限的资源，需要智能管理。

## 核心功能

### 1. 会话状态管理

追踪当前会话的活跃状态：

```python
session_state = {
    "active_variables": {},
    "pending_tasks": [],
    "intermediate_results": {},
    "conversation_turns": 0
}
```

### 2. 上下文窗口优化

智能摘要和压缩长对话。

**触发条件：**
- Token使用超过70%时触发压缩
- 单轮对话超过2000 tokens
- 明确要求压缩

### 3. 记忆注入

将长期记忆适时注入当前上下文：

```python
def inject_relevant_memory(current_task):
    memories = memory.search(task=current_task, limit=3)
    for memory in memories:
        if memory.relevance_score > 0.7:
            inject(memory.content, priority="high")
```

## 上下文优先级

| 优先级 | 内容 | 保留策略 |
|--------|------|---------|
| CRITICAL | 用户指令、工具结果 | 永不压缩 |
| HIGH | 最近对话、活跃变量 | 优先保留 |
| MEDIUM | 历史决策、结论 | 摘要保留 |
| LOW | 探索对话、闲聊 | 延迟保留 |

## 压缩示例

### 原始对话（约2000 tokens）
```
User: 实现REST API
User: 需要JWT认证
... [10轮后]
```

### 压缩后
```
[早期摘要]
- 需求：REST API + JWT认证
- 实现：完成基础CRUD + 认证
[最近5轮保持完整]
```

### 4. 角色注入（Prompt-Armory 集成）

**触发条件**：context-engine 加载 且 当前任务复杂度 ≥ 中（3+ 工具调用 或 2+ 模块/系统）

**流程**（全程静默，不告知用户）：
1. 从任务描述提取 1-3 个领域关键词
2. 调用 prompt-armory 的 search_all(keywords, limit=3)
3. 取 score ≥ 70 的最佳 1-2 条
4. 注入系统指令：
   `[角色注入] 你是 {name}（{source}, {score}/100）。请以该角色专业视角处理当前任务。`
5. 如果无高分命中 → 跳过

**质量要求**：
- 角色注入不改变用户指令，仅增强 Agent 视角
- 每次最多注入 2 个角色
- 注入内容不进入主上下文（追加到 system prompt）

## 最佳实践

1. **定期清理**：长任务完成后清理临时变量
2. **显式摘要**：重要结论用`memory.save()`持久化
3. **分块处理**：复杂任务使用`/new`开启新会话
4. **避免膨胀**：不重复相同信息

## 工具集成

- `memory.save()` — 保存关键上下文
- `session_search()` — 检索历史上下文
- `execute_code()` — 代码执行（隔离上下文）
- `terminal()` — 命令执行

## 参考资料

- `mimiraether-memory-nudge` — 记忆唤醒机制
- `mimiraether-context-compressor` — 压缩算法
- `mimiraether-cross-session` — 跨会话持久化
