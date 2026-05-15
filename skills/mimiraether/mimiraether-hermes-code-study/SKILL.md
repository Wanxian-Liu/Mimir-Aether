---
description: 系统化学习Hermes Agent源码，识别与MimirAether的差距，制定演进路线图
---

# MimirAether Hermes源码学习技能

## 用途
系统化学习Hermes Agent源码，识别与MimirAether的差距。

## 工作流程

### 1. 定位源码
```bash
# Hermes主项目位置
HERMES_PATH="/home/rayliu/.openclaw/projects/hermes-agent"

# 关键模块
ls $HERMES_PATH/environments/agent_loop.py
ls $HERMES_PATH/agent/context_compressor.py
ls $HERMES_PATH/agent/prompt_builder.py
```

### 2. 源码分析清单
- [ ] 读取完整源文件
- [ ] 识别核心类和接口
- [ ] 记录关键设计模式
- [ ] 提取常量配置
- [ ] 分析错误处理机制

### 3. MimirAether对比
```python
# MimirAether位置
MIMIR_PATH="$(git rev-parse --show-toplevel)"   # 或 export MIMIR_REPO_ROOT

# 检查对应文件
ls $MIMIR_PATH/agent/core_loop.py      # vs agent_loop.py
ls $MIMIR_PATH/agent/context_compressor.py
ls $MIMIR_PATH/agent/prompt_builder.py
```

### 4. 差距分析模板
```
### 功能X对比

**Hermes实现**:
- 关键代码片段
- 设计模式

**MimirAether现状**:
- 现有实现
- 缺失部分

**差距**:
1. ❌ 完全缺失
2. ⚠️ 部分实现
3. ✅ 已对齐
```

### 5. 记录学习结果
保存到: `skills/mimiraether/` (本仓库技能目录)

## 核心模块清单

| 模块 | Hermes路径 | MimirAether路径 | 优先级 |
|------|-----------|-----------------|--------|
| agent_loop | environments/agent_loop.py | agent/core_loop.py | P1 |
| context_compressor | agent/context_compressor.py | agent/context_compressor.py | P2 |
| prompt_builder | agent/prompt_builder.py | agent/prompt_builder.py | P3 |
| model_tools | model_tools.py | (集成) | P1 |
| toolsets | toolsets.py | tools/registry.py | P2 |
| hermes_state | hermes_state.py | (集成) | P2 |

## 关键设计模式记录

### 1. HermesAgentLoop
- 使用async/await
- 标准OpenAI tool_calls
- ThreadPoolExecutor (128 workers)
- AgentResult返回完整元数据

### 2. ContextCompressor
- 继承ContextEngine
- 迭代摘要更新
- 失败冷却机制
- Focus topic支持

### 3. PromptBuilder
- 平台提示系统
- 安全扫描
- 模型特定指导

## 学习成果（2026-04-29）

### Agent Loop 对比核心发现

**HermesAgentLoop（~500行）vs MimirAetherAgent（~110K）**
- Hermes: 纯执行引擎，职责单一，接收已准备好的 server + messages
- MimirAether: 全能型 Agent，自己管理模型/凭证/工具注册，过于臃肿
- 行动: 将 loop 逻辑提取为独立 `MimirAgentLoop`

**关键缺失**
1. 异步桥接层（`_get_tool_loop` / `_get_worker_loop`）— 导致 Event loop is closed
2. ContextEngine 抽象基类 — 无法插拔上下文引擎
3. 工具 deregister() — MCP 热更新不可用
4. 平台提示系统 — 不同平台使用相同提示
5. 模型特定执行指导 — Google/OpenAI 特殊处理

**已对齐模块**
- ToolRegistry（复制自 Hermes）
- 基础压缩逻辑（HermesStyleCompressor）
- 安全扫描（prompt_builder）
- 错误分类、凭证池、洞察引擎、内存管理等

完整分析见: **`<repo-root>/learnings/hermes_agent_loop_gap_analysis.md`**（将 `<repo-root>` 换为你的 clone 路径）

## 下一步
- 完成100天计划Phase 1剩余24天
- 每周总结进度
- 迭代改进学习方法
