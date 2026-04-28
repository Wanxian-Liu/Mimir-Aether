# Phase 1 R1: 沙盒执行 - 捕获错误

## 目标
验证工具系统当前状态，定位`_discover_tools()`缺失问题

## 执行时间
2026-04-29 03:50 GMT+8

## 发现的问题

### 问题1: MimirAether没有`_discover_tools()`函数
**现状**: 
- Hermes的`model_tools.py`有`_discover_tools()`函数(行132)，导入22个工具模块
- MimirAether的`model_tools.py`完全没有此函数

**影响**:
- 大部分工具从未被导入，因此从未注册到registry
- 当前只导入了`tools.builtin`和`tools.mimircore_tool`
- 其他工具如`terminal_tool`, `web_tools`, `memory_tool`, `delegate_tool`等从未注册

### 问题2: core_loop.py不调用model_tools
**现状**:
- core_loop.py使用`tools.registry.registry`直接
- 但只手动导入2个工具模块

**影响**: 工具注册表严重不完整

### 问题3: context_compressor阈值问题
**现状**:
- threshold_percent = 0.85 (85%)
- Hermes使用0.50 (50%)
- tail_token_budget固定4000

**影响**: 上下文压缩不及时，可能溢出

## 当前注册的工具有哪些?
```python
# 只注册了5个builtin工具 + mimircore_tool
# 缺少Hermes的核心工具
```

## R2准备: 根因分析
需要实现:
1. 添加`_discover_tools()`到MimirAether的model_tools.py
2. 在core_loop初始化时调用
3. 调整context_compressor阈值

## 验证命令
```bash
cd /home/rayliu/.openclaw/projects/MimirAether
python3 -c "
import sys
sys.path.insert(0, '.')
from tools.registry import registry
print('Total registered tools:', len(registry._tools))
print('Tool names:', list(registry._tools.keys()))
"
```
