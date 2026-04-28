# Hermes vs MimirAether: Agent Loop 深度对比分析

学习日期: 2026-04-29

## 1. Agent Loop 核心架构

### Hermes (agent_loop.py)
- **HermesAgentLoop** 是纯执行引擎，不负责模型初始化、系统提示构建
- 接收已准备好的 `server` 对象和 `messages` 列表
- 职责单一：运行 tool-calling loop，返回 `AgentResult`
- 支持 Phase 1 (OpenAI API) 和 Phase 2 (ManagedServer) 两种模式
- 使用 `handle_function_call()` 统一调度，通过 `model_tools.py` 中间层

### MimirAether (core_loop.py)
- **MimirAetherAgent** 是全能型 Agent：自己管理模型、凭证、系统提示、工具注册
- 职责过重：~110K 代码（Hermes agent_loop.py ~500行）
- 内部自建了 ToolRegistry（虽然委托到 Hermes 的 registry）
- 集成了 ContextCompressor、InsightsEngine、SkillManager、MemoryFencer

### 差距
1. ❌ MimirAether 核心 loop 过于臃肿，应该拆分为执行引擎 + 配置层
2. ⚠️ MimirAether 的 ToolRegistry 是兼容层，实际依赖 Hermes 的 registry
3. ✅ 学到了 Hermes 的 `AgentResult` 数据结构，MimirAether 有 `ExecutionMetadata`
4. ✅ 学到了 ThreadPoolExecutor 模式（128 workers），MimirAether 已复制

## 2. 工具系统

### Hermes (tools/registry.py + model_tools.py + toolsets.py)
- **三件套架构**: registry (注册) → model_tools (调度) → toolsets (分组)
- 工具自动注册：每个工具文件在模块级别调用 `registry.register()`
- 工具集系统：`TOOLSETS` 字典定义分组，支持组合（includes）
- `check_fn` 机制：运行时检查工具可用性（环境变量、依赖）
- `max_result_size_chars`：工具结果大小限制
- `deregister()`：MCP 动态工具发现的热更新

### MimirAether (tools/registry.py + toolsets.py)
- 直接复制了 Hermes 的 registry.py（完全一致）
- 但 `core_loop.py` 中的 `ToolRegistry` 是兼容层，委托到 `tools.registry.registry`
- 缺少 `model_tools.py` 的异步桥接层（`_get_tool_loop`, `_get_worker_loop`）

### 差距
1. ⚠️ 复制了 registry 但缺少异步桥接层（会导致 "Event loop is closed" 错误）
2. ❌ 缺少 `deregister()` 的 MCP 热更新场景使用
3. ❌ 缺少 `max_result_size_chars` 字段
4. ✅ toolsets.py 基本对齐

## 3. 上下文管理

### Hermes
- **ContextEngine** 抽象基类：定义 `should_compress()`, `compress()`, `update_from_response()`
- **ContextCompressor** 实现：基于 token 阈值的摘要压缩
  - 结构化摘要模板（Resolved/Pending 跟踪）
  - 迭代摘要更新（多次压缩保留信息）
  - Token-budget 尾部保护（非固定消息数）
  - 工具输出预裁剪（LLM 之前的低成本预处理）
  - 缩放摘要预算（按压缩内容比例）
  - 失败冷却（600 秒）
- 可插拔引擎：通过 plugins/context_engine/ 目录替换

### MimirAether (context_compressor.py)
- 实现了 `HermesStyleCompressor`，学习自 Hermes
- 但 `core_loop.py` 中的压缩逻辑是内联的，未使用 ContextEngine 抽象

### 差距
1. ⚠️ MimirAether 有压缩器但没有 ContextEngine 抽象基类
2. ❌ 缺少可插拔引擎机制
3. ❌ 缺少失败冷却机制
4. ❌ 缺少迭代摘要更新
5. ✅ 基础压缩逻辑已实现

## 4. Prompt 系统

### Hermes (prompt_builder.py)
- 纯函数式：所有函数 stateless
- 安全扫描：`_scan_context_content()` 检测 prompt injection
- 平台提示系统：不同平台（CLI, Telegram, Discord）有不同的提示
- 模型特定指导：Google, OpenAI, Developer Role 等
- 技能索引注入：`build_skills_system_prompt()`
- 上下文文件注入：`build_context_files_prompt()`
- 内存上下文构建：`build_memory_context_block()`

### MimirAether (prompt_builder.py)
- 50K 代码，功能丰富
- 有自己的安全扫描和安全提示系统
- 但缺少统一的平台提示系统

### 差距
1. ⚠️ MimirAether 的 prompt_builder 代码量相当但缺少平台提示系统
2. ❌ 缺少模型特定执行指导（Google, OpenAI 等）
3. ✅ 安全扫描已实现
4. ✅ 技能/内存/上下文注入已实现

## 5. Hermes 有但 MimirAether 缺失的关键模块

| 模块 | Hermes | MimirAether | 重要性 |
|------|--------|-------------|--------|
| gateway/ | 多平台消息网关 | 有简化版 | P1 |
| cron/ | 定时任务调度 | 有 scheduler/ | P1 |
| trajectory_compressor.py | 轨迹压缩(63K) | 有 trajectory.py | P2 |
| agent/display.py | 终端显示(旋转器,emoji) | 无 | P2 |
| agent/subdirectory_hints.py | 子目录提示 | 无 | P3 |
| agent/anthropic_adapter.py | Anthropic API适配 | 有(82K) | ✅ |
| agent/credential_pool.py | 凭证池 | 有(82K) | ✅ |
| agent/error_classifier.py | 错误分类 | 有(29K) | ✅ |
| agent/insights.py | 洞察引擎 | 有(51K) | ✅ |
| agent/memory_manager.py | 内存管理 | 有(21K) | ✅ |
| agent/model_metadata.py | 模型元数据 | 有(43K) | ✅ |
| agent/rate_limit_tracker.py | 速率限制 | 有(14K) | ✅ |
| agent/retry_utils.py | 重试工具 | 有(14K) | ✅ |
| agent/skill_utils.py | 技能工具 | 有(25K) | ✅ |
| agent/smart_model_routing.py | 智能路由 | 有(9K) | ✅ |
| agent/usage_pricing.py | 使用定价 | 有(22K) | ✅ |

## 6. 核心差距总结

### P0（必须修复）
1. **Agent Loop 过于臃肿**：MimirAetherAgent 110K vs HermesAgentLoop 500行
   - 应拆分：执行引擎 + 配置层 + 回调系统
   - 执行引擎应纯化：只负责 loop，不负责模型/凭证/工具注册

2. **缺少异步桥接层**：model_tools.py 的 `_get_tool_loop()` / `_get_worker_loop()`
   - 直接导致 "Event loop is closed" 错误
   - 每个线程需要持久化 event loop

### P1（重要差距）
3. **缺少 ContextEngine 抽象基类**：无法插拔上下文引擎
4. **工具系统缺少 deregister()**：MCP 热更新不可用
5. **缺少平台提示系统**：不同平台使用相同提示
6. **缺少模型特定执行指导**：Google/OpenAI 模型需要特殊处理

### P2（优化项）
7. **缺少 display.py**：终端显示体验不足
8. **缺少 trajectory_compressor**：轨迹压缩能力弱
9. **缺少 subdirectory_hints**：子目录感知能力

## 7. 行动建议

### 短期（本周）
1. 将 MimirAetherAgent 的 loop 逻辑提取为独立的 `MimirAgentLoop`
2. 添加异步桥接层（复制 Hermes 的 `_get_tool_loop` / `_get_worker_loop`）
3. 实现 ContextEngine 抽象基类

### 中期（本月）
4. 实现平台提示系统
5. 添加 deregister() 支持
6. 实现模型特定指导

### 长期（下月）
7. 实现 display.py
8. 增强 trajectory 压缩
9. 实现 subdirectory_hints
