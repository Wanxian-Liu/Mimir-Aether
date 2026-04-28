# MimirAether 1:1 对齐 Hermes - 第1模块：auxiliary_client

## 对比分析

### 规模对比
| 指标 | Hermes | MimirAether (当前) | MimirAether (new, 未完成) |
|------|--------|--------------------|---------------------------|
| 代码行数 | ~2700行 | ~370行 | ~190行 |
| Provider支持 | 10+ (OpenRouter, Nous, Codex, Anthropic, ZAI, Kimi, MiniMax, MiniMax-CN, Gemini, Copilot, Custom) | 5 (DeepSeek, Anthropic, MiniMax, OpenAI, Moonshot) | 同上 |
| API客户端 | OpenAI SDK (统一) | aiohttp (裸HTTP) | OpenAI SDK |
| 适配器 | Codex, Anthropic (3层) | 无 | 无 |

### 架构差距（设计模式层面）

#### 1. Provider解析链 ⭐ 最重要
Hermes: `_get_provider_chain()` → 可组合的 (label, try_fn) 元组列表
MimirAether: 无此概念，硬编码if-else级联

#### 2. 适配器模式
Hermes: `_AnthropicCompletionsAdapter`, `_CodexCompletionsAdapter` → 统一 `client.chat.completions.create()` 接口
MimirAether: 分别为每种API格式写独立的 `_call_xxx()` 函数

#### 3. 客户端缓存
Hermes: `_get_cached_client()` 按 (provider, async_mode, base_url, api_key, loop_id) 缓存
        `cleanup_stale_async_clients()` 防止跨循环死锁
MimirAether: 无缓存，每次创建新的 aiohttp session

#### 4. 任务路由
Hermes: `_resolve_task_provider_model()` → 优先级: 显式参数 > config.yaml > auto
MimirAether: 无此概念

#### 5. 付款/连接错误回退
Hermes: `_try_payment_fallback()`, `_is_payment_error()`, `_is_connection_error()`
MimirAether: 简单的try-except循环，无智能回退

#### 6. Anthropic兼容端点检测
Hermes: `_is_anthropic_compat_endpoint()`, `_convert_openai_images_to_anthropic()`
MimirAether: 无

#### 7. Vision专用解析
Hermes: `resolve_vision_provider_client()`, `get_available_vision_backends()`
MimirAether: 无

#### 8. Codex Responses API适配
Hermes: `_CodexCompletionsAdapter` 将 Responses API 流式输出转为 chat.completions 格式
MimirAether: 无

## 改进计划

### 阶段1: 重新设计 `auxiliary_client_new.py` → 覆盖核心架构
- [x] 保留已有的 Provider别名、凭证池集成、Config Helpers
- [ ] 添加 `_get_provider_chain()` 解析链架构
- [ ] 添加所有 `_try_*` 函数
- [ ] 添加 `_resolve_auto()` 自动检测
- [ ] 添加 `resolve_provider_client()` 中央路由
- [ ] 添加 Anthropic/Codex 适配器类
- [ ] 添加客户端缓存系统
- [ ] 添加任务路由
- [ ] 添加付款/连接回退
- [ ] 添加 `call_llm()` / `async_call_llm()` 中央入口

### 阶段2: 替换旧 `auxiliary_client.py`
- 将 `auxiliary_client_new.py` 改为正式版本
- 确保所有依赖模块兼容

### 阶段3: 测试集成
- 确保 context_compressor, web_tools, session_search 等模块正常工作
