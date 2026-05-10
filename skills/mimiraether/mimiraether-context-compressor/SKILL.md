---
auto_load: true
name: mimiraether-context-compressor
description: MimirAether上下文压缩器 - 基于Hermes设计的智能压缩系统，减少token消耗同时保留关键信息
---

# MimirAether Context Compressor

## 描述

MimirAether上下文压缩器 - 基于Hermes设计的智能压缩系统，减少token消耗同时保留关键信息。

**设计来源**: `~/.openclaw/projects/hermes-agent/agent/context_compressor.py`

## 核心设计

### 分层保护策略

```
┌─────────────────────────────────────────────────────────────┐
│  HEAD        │  MIDDLE (Compressible)  │  TAIL (Protected) │
│  Protected   │  LLM Summarization      │  Token Budget     │
│  ~3 messages │  Structured Summary     │  ~20K tokens      │
└─────────────────────────────────────────────────────────────┘
```

- **HEAD保护**: 系统提示 + 首次对话交换
- **MIDDLE压缩**: LLM生成结构化摘要
- **TAIL保护**: 最近消息按token预算保护

### 两阶段压缩

1. **阶段1 - 工具输出修剪**（无LLM调用）
   - 替换旧工具结果为占位符 `[Old tool output cleared]`
   - 仅修剪 >200 字符的内容

2. **阶段2 - LLM结构化摘要**
   - 缩放摘要预算（压缩内容的20%）
   - 增量摘要：保留前次摘要，新内容增量更新

## 结构化摘要模板

```markdown
## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
[User preferences, coding style, constraints]

## Progress
### Done
[Completed work with specific file paths, commands, results]
### In Progress
[Work currently underway]
### Blocked
[Any blockers or issues]

## Key Decisions
[Important technical decisions and why]

## Resolved Questions
[Questions already answered - include answers]

## Pending User Asks
[Unanswered questions/requests - "None." if none]

## Relevant Files
[Files read, modified, created]

## Remaining Work
[What remains - framed as context, not instructions]

## Critical Context
[Specific values, errors, configs]

## Tools & Patterns
[Tools used and effective patterns]
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| threshold_percent | 0.50 | 触发压缩的token阈值（50%上下文） |
| protect_first_n | 3 | 头部保护消息数 |
| protect_last_n | 20 | 尾部保护消息数 |
| summary_target_ratio | 0.20 | 摘要占压缩内容的比例 |

## 实现参考

```python
# 核心逻辑流程
def compress_context(messages):
    # 1. 工具输出修剪
    pruned = prune_old_tool_results(messages)
    
    # 2. 分离头/中/尾
    head, middle, tail = partition_messages(pruned)
    
    # 3. 生成摘要
    summary = generate_structured_summary(middle)
    
    # 4. 重组消息
    return head + [summary] + tail
```

## 失败保护

- 摘要失败后10分钟冷却期
- 防止重复调用失败模型
- 降级策略：直接丢弃中间消息（无摘要）

## 触发条件

```python
should_compress = prompt_tokens >= threshold_tokens
# threshold_tokens = context_length * threshold_percent
```

## 使用场景

1. **手动触发**: `/compress` 或 `/compress <focus_topic>`
2. **自动触发**: prompt_tokens 超过阈值
3. **焦点压缩**: 指定主题优先保留

---
_灵感来源: Hermes Agent context_compressor.py v2_
