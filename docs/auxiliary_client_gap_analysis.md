# auxiliary_client 差距分析 & 改进计划

## 量化差距
- Hermes: 2614行 / 110KB
- MimirAether: 438行 / 13KB
- **差距: 2176行 / 97KB（只有17%的覆盖度）**

## 架构差距逐项分析

### 1. Provider路由解析链 (Resolution Chain) - 最核心差距
**Hermes:** 完整的6级auto-detection链:
  OpenRouter → Nous Portal → Custom Endpoint → Codex OAuth → API-key Providers → Anthropic Native
  每级有独立的 `_try_*` 函数，含凭证池集成 + fallback逻辑

**MimirAether:** 硬编码5个provider，简单env-var lookup，无凭证池集成，无auto链

**改进:** 重构为Provider Chain模式，每级独立 `_try_*` 函数

### 2. Client Adapter模式 - 关键设计模式
**Hermes:** 通过adapter模式统一所有provider到 `.chat.completions.create()`:
  - `_CodexCompletionsAdapter` (Responses API → Chat Completions)
  - `_AnthropicCompletionsAdapter` (Messages API → Chat Completions)
  - `CodexAuxiliaryClient`, `AnthropicAuxiliaryClient`

**MimirAether:** 用原始aiohttp直接调API，无adapter抽象

**改进:** 实现adapter模式，统一API接口

### 3. Client缓存机制
**Hermes:** `_client_cache` + `_client_cache_lock` + `_get_cached_client()`
  处理async client的loop绑定问题、stale loop检测

**MimirAether:** 无缓存，每次都创建新client

**改进:** 实现线程安全的client缓存

### 4. 支付/额度耗尽Fallback
**Hermes:** `_try_payment_fallback()` 检测HTTP 402 + credit exhaustion
  自动跳转到下一个provider

**MimirAether:** `async_call_with_failover()` 手动指定provider列表，无自动检测

**改进:** 实现自动payment/connection error fallback

### 5. Vision/Multimodal路由
**Hermes:** `resolve_vision_provider_client()` 独立vision backend链
  MiniMax图片格式转换(`_convert_openai_images_to_anthropic`)

**MimirAether:** 无vision支持

**改进:** 添加vision provider路由

### 6. 任务特定配置
**Hermes:** `_resolve_task_provider_model()` 从config.yaml读per-task配置
  auxiliary.compression.provider/model 等

**MimirAether:** 无此功能

**改进:** 实现task-config解析

### 7. 响应提取增强
**Hermes:** `extract_content_or_reasoning()` 包含:
  - think block正则剥离
  - reasoning/reasoning_content/reasoning_details多层降级

**MimirAether:** 简单提取 choices[0].message.content 或 reasoning_content

**改进:** 增强响应提取逻辑

### 8. 其他Hermes有、MimirAether没有的:
- Provider别名（_PROVIDER_ALIASES）
- 环境变量污染检测（OPENAI_BASE_URL stale warning）
- response验证（_validate_llm_response）
- 模块级neuter_async_httpx_del
- shutdown_cached_clients / cleanup_stale_async_clients
- Nous Portal extra_body tags
- max_tokens vs max_completion_tokens智能切换

## 改进优先级
1. **P0: Provider Chain重构** - 引入 `_try_*` 模式，auto-detection链
2. **P0: Client Adapter模式** - Anthropic/Codex adapter，统一接口
3. **P1: Client缓存** - 线程安全缓存，loop绑定处理
4. **P1: Payment Fallback** - 自动额度耗尽切换
5. **P1: Vision路由** - Vision backend独立链 + 图片格式转换
6. **P2: Task Config** - 从config读取per-task配置
7. **P2: 响应提取增强** - think block剥离，多层降级
8. **P2: 辅助功能** - provider别名，env检测，response验证
