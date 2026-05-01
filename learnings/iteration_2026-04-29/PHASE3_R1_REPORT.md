# Phase 3 R1: agent_loop重构 - 沙盒执行

## 执行时间
2026-04-29 04:10 GMT+8

## 问题
core_loop.py过大（2775行），难以维护。

## 现状分析

### 文件结构
```
core_loop.py (2775行)
├── 工具类 (lines 93-262)
│   ├── MessageRole
│   ├── Message
│   ├── ToolCall
│   ├── ToolResult
│   ├── ToolError
│   ├── ExecutionMetadata
│   ├── Plan
│   ├── ExecutionResult
│   └── ToolRegistry
├── MimirAetherAgent类 (lines 268-2619, ~2351行)
│   ├── 凭证/配置管理 (~450-680)
│   ├── 系统提示构建 (~680-750)
│   ├── 流式处理 (~750-800)
│   ├── 中断处理 (~770-800)
│   ├── 工具调用处理 (~820-950)
│   ├── API调用 (~950-1550)
│   ├── 工具执行 (~1550-2250)
│   ├── 技能管理 (~2250-2350)
│   └── 轨迹/会话 (~2350-2600)
└── 独立函数 (lines 2622-2775)
    ├── skill_view_func
    ├── skills_list_func
    └── skill_manage_func
```

### 职责混杂问题
1个类超过2300行，职责包括：
- API调用
- 工具执行
- 凭证管理
- 流式处理
- 技能管理
- 会话管理
- Hook系统

## 建议拆分方案

### 方案A: 按职责拆分（推荐）
```
agent/
├── core_loop.py      # 主循环入口 (~500行)
├── message_handler.py # 消息处理 (~400行)
├── tool_executor.py  # 工具执行 (~400行)
├── state_manager.py  # 状态管理 (~300行)
├── api_client.py     # API调用 (~400行)
├── types.py         # 数据类型定义 (~200行)
└── skill_funcs.py   # 技能函数 (~150行)
```

### 方案B: 渐进式拆分
先提取独立函数和类型定义，再逐步拆分类。

## R2准备: 根因分析和拆分方案
