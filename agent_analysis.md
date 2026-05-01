# MimirAether Agent 模块差距分析报告

**分析日期**: 2026-04-27  
**对比源**: hermes-agent/agent/  
**对比目标**: MimirAether/agent/  

---

## 1. Hermes有但MimirAether没有的文件

| 文件 | 重要性 | 处理建议 |
|------|--------|----------|
| `copilot_acp_client.py` | ⭐ 可选 | ⚠️ 条件复制 |
| `display.py` | ⭐⭐ 中等 | ⚠️ 部分需要 |
| `memory_provider.py` | ✅ 已覆盖 | 无需处理 |

---

## 2. 详细分析

### 2.1 `memory_provider.py` — ✅ 已覆盖，无需处理

**结论**: MimirAether的`memory_manager.py`已包含完整的`MemoryProvider`抽象基类。

MimirAether的`memory_manager.py`实现了与Hermes `memory_provider.py`完全相同的接口：

| 接口方法 | Hermes | MimirAether |
|----------|--------|-------------|
| `name` (property) | ✅ | ✅ |
| `is_available()` | ✅ | ✅ |
| `initialize()` | ✅ | ✅ |
| `system_prompt_block()` | ✅ | ✅ |
| `prefetch()` | ✅ | ✅ |
| `queue_prefetch()` | ✅ | ✅ |
| `sync_turn()` | ✅ | ✅ |
| `get_tool_schemas()` | ✅ | ✅ |
| `handle_tool_call()` | ✅ | ✅ |
| `shutdown()` | ✅ | ✅ |
| `on_turn_start()` | ✅ | ✅ |
| `on_session_end()` | ✅ | ✅ |
| `on_pre_compress()` | ✅ | ✅ |
| `on_delegation()` | ✅ | ✅ |
| `get_config_schema()` | ✅ | ✅ |
| `save_config()` | ✅ | ✅ |
| `on_memory_write()` | ✅ | ✅ |

MimirAether还额外添加了中文注释和`build_memory_context_block()`、`sanitize_context()`等辅助函数。

---

### 2.2 `display.py` — ⚠️ 部分需要

**文件大小**: ~600行  
**功能**: CLI视觉反馈层

**包含的子模块**:

| 子模块 | 功能 | MimirAether状态 |
|--------|------|----------------|
| `LocalEditSnapshot` | 文件编辑前后快照 | ❌ 缺失 |
| `set_tool_preview_max_len()` | 工具预览长度配置 | ❌ 缺失 |
| `get_tool_emoji()` | 工具emoji获取 | ❌ 缺失 |
| `build_tool_preview()` | 工具调用单行预览 | ❌ 缺失 |
| `capture_local_edit_snapshot()` | 快照捕获 | ❌ 缺失 |
| `extract_edit_diff()` | 从patch结果提取diff | ❌ 缺失 |
| `render_edit_diff_with_delta()` | 渲染diff到CLI | ❌ 缺失 |
| `KawaiiSpinner` | 可爱的CLI旋转动画 | ❌ 缺失 |
| `get_cute_tool_message()` | 工具完成消息格式化 | ❌ 缺失 |
| `format_context_pressure()` | 上下文压力显示 | ❌ 缺失 |

**建议**: 
- 如果MimirAether是纯API/Gateway服务，不需要CLI，`display.py`可以完全不需要
- 如果需要CLI交互，建议选择性移植`KawaiiSpinner`和工具消息格式化
- 核心agent逻辑不需要此文件

**与Hermes的集成点**: 依赖`hermes_cli.skin_engine`，如果MimirAether不使用Hermes CLI皮肤系统，需要重写或mock相关函数。

---

### 2.3 `copilot_acp_client.py` — ⚠️ 条件复制

**文件大小**: ~400行  
**功能**: GitHub Copilot ACP的OpenAI兼容适配器

**核心能力**:
- 将Hermes请求转发到`copilot --acp` CLI
- 处理JSON-RPC协议的session/prompt交互
- 支持文件系统操作（read_text_file, write_text_file）
- 解析`<tool_call>`标签提取函数调用
- 兼容OpenAI ChatCompletion接口

**重要性评估**:
- ⭐⭐ **中低优先级** — 这是Hermes特有的Copilot集成
- MimirAether作为独立AI助手，不需要绑定GitHub Copilot
- 如果未来需要支持Copilot作为后端供应商，才需要此文件

**建议**: **暂时不需要复制**

理由：
1. MimirAether应使用标准的Anthropic/OpenAI API，不依赖Copilot CLI
2. 如果未来需要多后端支持，应通过`smart_model_routing.py`扩展
3. 此文件与核心agent逻辑解耦，可独立添加

---

## 3. 差距总结

### 3.1 核心功能对比

| 功能模块 | Hermes | MimirAether | 差距 |
|----------|--------|-------------|------|
| Agent核心 | `core_loop` | `core_loop.py` | ✅ 已有 |
| 工具执行 | `turn_loop` | `turn_loop.py` | ✅ 已有 |
| 子代理池 | `subagent` | `subagent.py` | ✅ 已有 |
| 记忆管理 | `memory_provider` | `memory_manager.py` | ✅ 已覆盖 |
| 上下文压缩 | `context_compressor` | `context_compressor.py` | ✅ 已有 |
| 模型路由 | `smart_model_routing` | `smart_model_routing.py` | ✅ 已有 |
| CLI展示 | `display.py` | ❌ | ⚠️ 可选 |
| Copilot集成 | `copilot_acp_client` | ❌ | ⚠️ 不需要 |

### 3.2 MimirAether独有的文件（Hermes没有）

```
chat_interface.py     # 对话接口封装
core_loop.py          # 核心循环（改进版）
json_repair.py        # JSON修复工具
session_manager.py    # 会话管理
subagent.py           # 子代理池
turn_loop.py          # Turn管理
usage_pricing.py      # 使用量计费
test_*.py             # 测试文件
```

---

## 4. 建议行动项

### 高优先级
- ✅ **无** — 核心模块已完整对齐

### 中优先级
- ⚠️ 如需CLI支持：考虑选择性移植`display.py`中的工具消息格式化函数
- ⚠️ 如需Copilot支持：复制`copilot_acp_client.py`并适配

### 低优先级
- 📝 `display.py`中的`KawaiiSpinner`类可作为CLI动画的参考实现
- 📝 `format_context_pressure()`的上下文压力可视化逻辑可借鉴

---

## 5. 最终结论

**MimirAether Agent核心模块已与Hermes对齐，无需紧急补充。**

- `memory_provider.py`: ✅ 已在`memory_manager.py`中以更完整的形式实现
- `display.py`: ⚠️ CLI相关，MimirAether如果是纯API服务则不需要
- `copilot_acp_client.py`: ⚠️ 特定于Hermes的Copilot集成，MimirAether不需要

**核心差距**: 无
**建议**: 保持现状，按需选择性补充CLI展示层功能
