# PI-L05: 测试框架（可移植契约测试）— MimirAether 对照

> 只读学习，不复制 TS 文件、不修改 Mimir 代码。

## 源

- pi-agent: `coding-agent/test/suite/harness.ts` (208行, `createHarness` + `Harness` 类型), `test/test-harness.test.ts` (321行, harness 自测)
- MimirAether: `tests/tools/test_session_search_usage_baseline.py` (74行), `tests/` 目录下 15+ 测试文件

## 5 条异同

### 相同

1. **pytest / vitest 当代测试框架**：pi 用 vitest（describe/it/expect），Mimir 用 pytest（def test_ / assert）。两者都支持 setup/teardown、fixture 注入。
2. **可重复隔离环境**：pi 的 `createTempDir()` + `cleanup()` 清理临时目录；Mimir 使用 `tmp_path` fixture（pytest 内置）自动管理临时目录。
3. **Mock 真实 provider**：pi 用 `FauxProviderRegistration` + `registerFauxProvider()` 模拟 LLM 响应，不连真实 API。Mimir 用 `LlmInvocationPort` protocol 的测试替身（`_BuiltinLlmBackend` 可被 patch）。
4. **事件订阅验证**：pi 的 `harness.eventsOfType<T>()` 按类型过滤 AgentSessionEvent，验证 event 是否触发。Mimir 测试直接检查数据库状态、log 行或 JSONL 内容。
5. **渐进式断言**：pi 测试检查 `assistantTexts.length` → `callCount` → `stopReason`；Mimir 测试检查 `out["total_sessions"]` → `out["sessions_with_session_search"]`。

### 不同

1. **Harness 封装粒度**：pi 有完整的 `createHarness()` 工厂，返回 `Harness` 接口（session/sessionManager/faux/models/events/cleanup 都在一个对象上）。Mimir 的测试是分散的——每个 test file 手动创建 `SessionDB`、`tmp_path`、导入被测试函数，无统一 Harness 抽象。
2. **Faux Provider（伪造 LLM）**：pi 的 `registerFauxProvider()` 可注册多个 faux 模型，`setResponses()` / `appendResponses()` 控制 LLM 输出序列（支持文本 + tool_call 多步响应）。Mimir 无等价的 Faux Provider——依赖 `unittest.mock.patch` 或 callers_mixin 的 protocol 替换。
3. **契约测试的可移植性**：pi 的 harness 是**独立 npm 可发布单元**——其他项目可通过 `import { createHarness } from "@earendil-works/pi-coding-agent/test"` 复用。Mimir 的测试是**内联的**——每个 test file 直接 import 被测模块的内部细节。
4. **Tool execution 验证深度**：pi 测试可以直接验证 `tool_execution_start/tool_execution_update/tool_execution_end` 事件序列。Mimir 验证工具执行结果需要通过 `session_search` 或 JSONL 后处理。
5. **清理/退出保证**：pi 的 `afterEach` 总是调用 `harness.cleanup()`（删除临时目录 + session.dispose() + fauxProvider.unregister()）。Mimir 依赖 pytest 的 `tmp_path` 自动清理，但无 dispose/unregister 概念。

## 可借鉴（Mimir 落点）

1. **统一测试 Harness**：为 Mimir agent 测试创建 `create_test_harness()` 工厂，封装 `SessionDB` + `tmp_path` + `mock_model` + `event_collector` + `cleanup`，减少重复样板代码。
2. **Faux Provider 预置**：实现一个轻量 `FauxLlmProvider`，支持 `set_responses(sequence)` 精确控制 LLM 输出顺序，避免 unittest.mock.patch 的样板。
3. **事件订阅验证器**：pi 的 `eventsOfType` 模式可用于验证 Mimir 的 `record_tool_call` 调用链——测试可断言「工具 X 被执行了 N 次」或「错误被正确记录」。

## 明确不做

1. **npm 可发布抽象**：Mimir 不需要独立的 test-suite 包，统一 harness 的边界在仓库内即可。
2. **TUI/扩展测试**：pi 的 Extension 测试绑定于 Ink UI 框架，Mimir 无 TUI 因此不需要。
