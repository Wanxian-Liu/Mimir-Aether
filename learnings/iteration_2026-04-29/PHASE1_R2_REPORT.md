# Phase 1 R2: 根因分析 - 3种修复方案

## 执行时间
2026-04-29 03:52 GMT+8

## 问题确认

### 当前状态
- MimirAether只注册了9个工具（4个预加载 + 5个builtin）
- Hermes注册了44个工具（通过`_discover_tools()`）
- 差距: 35个工具未注册

### 根因
`_discover_tools()`函数从未在MimirAether的`model_tools.py`中实现

## 3种修复方案

### 方案A: 完整复制Hermes的`_discover_tools()` (推荐)
**思路**: 将Hermes的`_discover_tools()`复制到MimirAether

**优点**:
- 与Hermes 100%兼容
- 自动发现所有工具
- 支持MCP和Plugin扩展

**缺点**:
- 需要确保所有Hermes工具在MimirAether中存在
- 部分工具可能缺失或接口不同

**实施**:
```python
# model_tools.py 添加:
def _discover_tools():
    _modules = [
        "tools.web_tools",
        "tools.terminal_tool",
        "tools.file_tools",
        "tools.vision_tools",
        "tools.mixture_of_agents_tool",
        "tools.image_generation_tool",
        "tools.skills_tool",
        "tools.skill_manager_tool",
        "tools.browser_tool",
        "tools.cronjob_tools",
        "tools.rl_training_tool",
        "tools.tts_tool",
        "tools.todo_tool",
        "tools.memory_tool",
        "tools.session_search_tool",
        "tools.clarify_tool",
        "tools.code_execution_tool",
        "tools.delegate_tool",
        "tools.process_registry",
        "tools.send_message_tool",
        "tools.homeassistant_tool",
    ]
    for mod_name in _modules:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("Could not import tool module %s: %s", mod_name, e)

_discover_tools()
```

### 方案B: 仅导入MimirAether已有的工具
**思路**: 只导入MimirAether实际存在的工具模块

**优点**:
- 更安全，不会尝试导入不存在的模块
- 减少错误日志

**缺点**:
- 需要维护一个工具列表
- 可能遗漏未来添加的工具

### 方案C: 在core_loop.py初始化时导入
**思路**: 在AgentCore初始化时导入所有工具

**优点**:
- 显式控制导入时机
- 可以在导入失败时回退

**缺点**:
- 分散了工具发现的逻辑
- 违反了单一职责原则

## 推荐方案A

理由:
1. 与Hermes设计一致
2. 自动支持未来添加的工具
3. 错误处理机制完善
4. 支持MCP/Plugin扩展点

## R3准备: 实施修复
