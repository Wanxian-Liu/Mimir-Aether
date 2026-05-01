# auxiliary_client.py 阶段1改进计划

## 问题诊断
- MimirAether: 438行 vs Hermes: 2614行 (仅17%覆盖)
- **3个关键函数缺失**: `get_async_text_auxiliary_client`, `get_auxiliary_extra_body`, `resolve_vision_provider_client`
- 工具模块(web_tools/vision_tools/browser_tool)导入这些不存在函数 → 运行时崩溃
- 无Provider Chain模式、无Client Adapter、无缓存机制、无Payment Fallback

## 阶段1: Provider Chain + Client Adapter + 缺失函数 (P0)

### 1.1 Provider Chain重构
- 实现 `_try_openrouter()`, `_try_custom_endpoint()`, `_try_codex()`, `_try_anthropic()`, `_resolve_api_key_provider()`
- 实现 `_get_provider_chain()` 返回有序检测链
- 实现 `_resolve_auto()` 完整auto-detection
- 支持从MimirAether自身的credential_pool获取凭证

### 1.2 Client Adapter模式
- `_AnthropicCompletionsAdapter` - 将Anthropic Messages API适配为chat.completions
- `AnthropicAuxiliaryClient` - 封装原生Anthropic客户端
- `_to_async_client()` - 同步→异步客户端转换

### 1.3 缺失函数实现
- `get_async_text_auxiliary_client(task)` - 返回异步文本客户端
- `get_auxiliary_extra_body()` - 返回额外请求体
- `resolve_vision_provider_client()` - Vision任务提供商路由

### 1.4 增强call_llm/async_call_llm
- 统一入口，支持task参数 → per-task配置
- 支持Payment Fallback
- 支持Client缓存
- 提取 `_build_call_kwargs()` 统一参数构建

## 不照抄Hermes，而是学设计模式
- Provider Chain: 每级独立try函数，通过列表组装
- Client Adapter: 接口统一为.chat.completions.create()
- Client Cache: 线程安全字典，含loop绑定检测
- Payment Fallback: 402检测+自动切换
