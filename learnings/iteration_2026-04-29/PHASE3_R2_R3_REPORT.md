# Phase 3 R2/R3: agent_loop重构 - 分析与计划

## 执行时间
2026-04-29 04:15 GMT+8

## 发现

### 1. MimirAetherAgent类过于庞大
- **行数**: ~2351行 (line 268-2619)
- **问题**: 单一类包含太多职责

### 2. 存在死代码
- `skill_view_func`, `skills_list_func`, `skill_manage_func` (lines 2622-2775)
- 与`_register_builtin_tools`中导入的别名冲突
- 实际使用别名版本，死代码约150行

### 3. 数据类型分散
- `MessageRole`, `Message`, `ToolCall`, `ToolResult`等 (lines 93-230)
- 与`iteration_budget.py`等模块分离不完全

## 推荐的模块拆分方案

```
agent/
├── __init__.py
├── core_loop.py           # 主循环入口 (~500行)
│   ├── MimirAetherAgent类
│   ├── 消息类型定义 (MessageRole等)
│   └── 辅助函数
├── message_handler.py     # 消息处理 (~400行)
│   ├── _build_full_messages
│   ├── _strip_think_blocks
│   └── _extract_reasoning_from_response
├── tool_executor.py       # 工具执行 (~400行)
│   ├── _execute_tools
│   ├── _execute_single_tool
│   ├── _deduplicate_tool_calls
│   └── _repair_tool_call
├── api_client.py          # API调用 (~400行)
│   ├── _stream_openai_compatible
│   ├── _call_model_with_tokens
│   └── _call_anthropic_api
├── state_manager.py       # 状态管理 (~300行)
│   ├── reset
│   ├── _restore_session
│   ├── trajectory相关
│   └── hook系统
├── skill_funcs.py         # 技能函数 (~150行)
│   ├── SKILL_TOOL_SCHEMAS
│   ├── SKILL_MANAGE_SCHEMA
│   └── (remove dead code)
└── types.py              # 数据类型 (~150行)
    ├── MessageRole
    ├── Message
    ├── ToolCall
    └── ...
```

## 风险评估

- **高风险**: 拆分MimirAetherAgent类可能破坏现有功能
- **中风险**: 需要更新所有导入点
- **低风险**: 移除死代码（skill_funcs）

## 决策

鉴于Phase 3是大型重构任务（高风险），建议：
1. 将Phase 3标记为"需要更仔细的计划"
2. Phase 4和Phase 5可以并行进行（prompt_builder增强和工具系统增强）

## R4准备: 执行低风险更改（移除死代码）
