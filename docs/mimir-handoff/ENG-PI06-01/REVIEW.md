# ENG-PI06-01: REVIEW.md

## 请 Cursor 重点看

1. **FauxLlmProvider 的 protocol 兼容性** — `call_model_with_tokens(messages, session_id)` 签名与 `agent/llm_port.py` 的 `LlmInvocationPort` Protocol 对齐。确认 async 签名和返回 `(dict, float)` tuple。

2. **conftest.py 的 autouse 隔离与 harness fixture 不冲突** — 现有的 `_isolate_mimir_test_runtime` autouse fixture 已经设 `MIMIR_AETHER_HOME` 到 tmp_path。`harness` fixture 新增 SessionDB 创建，两者在同一个 tmp_path 下不冲突。

3. **原始测试改名保留** — 原有测试函数加了 `_original` 后缀但保持完全相同的逻辑，确保回归覆盖。新测试名与原测试名相同（无 `_original` 后缀）——确认所有测试平台不会因同名冲突（Python 函数重名会覆盖，所以我用了不同名字）。

## 已知未做

1. **无 `test_session_search_indexer.py` 迁移** — 该文件使用 `SessionSearchDB`（非 `SessionDB`），不适合当前 harness 设计。如需支持可在后续迭代添加。
2. **无 `--one-shot` CLI** — 这是 PI-L06 第 3 条（`ENG-CLI-01`），未在本粒实现。
3. **无工具执行事件流** — 这是 PI-L06 第 2 条（`ENG-TOOL-01`），未在本粒实现。
4. **无扩展示例（如 mock agent loop）** — 当前 harness 聚焦 SessionDB + FauxLlmProvider。完整 agent loop mock 需要 `LlmInvocationPort` 替换，建议在 `ENG-SF-01` 中验证。

## 预检清单

- [x] tier0 运行（677 passed, 4 failed pre-existing）
- [x] 3 条新测试全部通过
- [x] 原始测试保留（_original 后缀）
- [x] 未改 agent/gateway/tools
- [x] 未 git push
- [x] handoff 4 文件完整
