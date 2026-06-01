# PI-L04: 多 Provider 抽象 — MimirAether 对照

> 只读学习，不复制 TS 文件、不修改 Mimir 代码。

## 源

- pi-agent: `packages/ai/src/types.ts`（`Model`/`Provider`/`Api` 类型），`models.ts`（registry/`getModel`），`models.generated.ts`，`providers/register-builtins.ts`（36+ provider 注册），`env-api-keys.ts`
- MimirAether: `agent/model_metadata.py`（1130行, 上下文长度表+前缀匹配），`agent/llm_port.py`（`LlmInvocationPort` protocol），`agent/callers_mixin.py`（`_BuiltinLlmBackend`）

## 5 条异同

### 相同

1. **多 provider 支持**：两方都支持 DeepSeek/Anthropic/OpenAI/Google/Groq/OpenRouter 等 20+ provider。
2. **API key 从环境变量解析**：pi 从 `process.env` 读取 `env-api-keys.ts` 映射表（`ANTHROPIC_API_KEY`→`anthropic`）；Mimir 从 `os.environ` 读取 `.env` 文件中的密钥。
3. **模型元数据注册**：pi 有 `models.generated.ts`（编译时生成的模型列表），Mimir 有 `model_metadata.py`（运行时从 OpenRouter 获取 + YAML 缓存 + 默认表）。
4. **provider 前缀路由**：pi 通过 `api-registry.ts` 按 `Model.api` 字段路由到不同 provider 模块；Mimir 通过 `model_metadata._PROVIDER_PREFIXES` + `DEFAULT_CONTEXT_LENGTHS` 做前缀匹配。
5. **context window 管理**：两方都跟踪模型的 context length 以做上下文修剪决策。

### 不同

1. **类型安全 vs 运行时**：pi 使用 TypeScript 泛型（`Model<TApi>`）+ 编译时生成 `models.generated.ts`，provider 和 API 类型严格匹配。Mimir 是纯 Python 运行时——`model_metadata.py` 从 OpenRouter API 拉取模型列表，动态解析 `max_completion_tokens`，无编译期类型约束。
2. **API 适配器粒度**：pi 以 **API 协议**为单位（`openai-completions`、`openai-responses`、`anthropic-messages`、`google-generative-ai`、`bedrock-converse-stream`、`mistral-conversations`），多个 provider 可共享同一协议。Mimir 以 **provider** 为单位（`anthropic_adapter.py` + `callers_mixin` 内嵌 OpenAI 协议调用），协议与 provider 耦合。
3. **OAuth 认证**：pi 支持 `/login` OAuth 流程（Anthropic/OpenAI Codex/GitHub Copilot 的 device code flow），`oauth.ts` + `auth-storage.ts` 管理令牌持久化。Mimir 只有 API Key + 环境变量，无交互式 OAuth。
4. **模型列表自动更新**：pi 在每次发布时由 `generate-models.ts` 脚本编译生成 `models.generated.ts`。Mimir 运行时动态请求 OpenRouter `/api/v1/models`，缓存到 YAML 文件（跨会话持久化）。
5. **LlmInvocationPort 协议**：Mimir 定义了 `LlmInvocationPort` Protocol 接口（`call_model_with_tokens`），是替换性 seam，可通过依赖注入替换后端。pi 采用 `StreamFn` 函数签名 + `registerApiProvider` 插件化注册，更灵活但无 protocol 契约。

## 可借鉴（Mimir 落点）

1. **API 层抽象**：将现有 Anthropic/OpenAI 适配器按协议（`openai-completions`、`anthropic-messages`）重构，分离协议代码与 provider 特定逻辑。
2. **OAuth 认证流**：如果未来需要 GitHub Copilot/Claude Code 订阅集成，可参考 pi 的 `device-code.ts` + `auth-storage.ts` 实现。
3. **成本计算标准化**：pi 的 `calculateCost` 函数（按 token 单价 / 1M 计算）可作为 Mimir 成本追踪模块的参考。

## 明确不做

1. **编译时模型生成**：Mimir 运行时的 OpenRouter 动态模型发现更灵活，无 Node 编译管线依赖。
2. **36+ provider 全覆盖**：Mimir 生产只需 3–4 个主要 provider（DeepSeek/Anthropic/OpenAI），扩展过多增加维护负担。
3. **registration 插件系统**：`api-registry.ts` 的 `registerApiProvider` 动态注册模式对 Mimir 当前单端口结构无增益。
