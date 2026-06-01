# ENG-PI06-01: 统一测试 Harness — SUMMARY

## 做了什么

1. **`tests/conftest.py`** 添加：
   - `FauxLlmProvider` — 轻量 mock LLM，支持 `set_responses()` / `append_responses()` 精确控制输出序列，匹配 `LlmInvocationPort` protocol
   - `MimirHarness` dataclass — 统一测试上下文（`tmp_path` + `db_path` + `SessionDB` + `FauxLlmProvider` + `cleanup()`）
   - `create_mimir_harness(tmp_path)` 工厂函数
   - `harness` pytest fixture（自动 teardown 清理）

2. **迁移 2 个现有测试文件** 示范 harness 用法：
   - `tests/tools/test_session_search_usage_baseline.py` — `test_baseline_counts_sessions_with_search` 使用 `harness.db` + `harness.db_path`
   - `tests/tools/test_mimir_ops_tool.py` — `test_session_reset_pending_roundtrip` 使用 `harness.tmp_path`

3. **新增 1 个示范测试**：
   - `test_harness_faux_llm_provider` — 演示 FauxLlmProvider 三种响应控制、call_count 计数、默认 fallback

4. **保留原有测试**（`_original` 后缀）确保回归覆盖。

## 为何做

PI-L06 立项第 1 条：减少测试样板代码 40%+，新测试 5 行内完成 setup-assert-cleanup。此前每个测试手动 `SessionDB(tmp_path)` + 手动 cleanup，无统一 mock LLM provider。

## 风险

极低。只添加新代码（conftest.py 的 class/fixture）和追加测试用例。原有测试全部保留且通过。

## 建议 commit message

```
feat(tests): 统一测试 Harness — FauxLlmProvider + create_mimir_harness + harness fixture (#ENG-PI06-01)

- tests/conftest.py: FauxLlmProvider (mock LLM), MimirHarness (统一上下文), 
  create_mimir_harness(), harness fixture (自动 cleanup)
- 迁移 2 个测试示范 harness 用法 (test_session_search_usage_baseline, 
  test_mimir_ops_tool)
- 新增 1 个 FauxLlmProvider 示范测试
- 保留原始测试确保回归覆盖
- tier0: 677 passed, 4 failed (pre-existing L2/L3 retrieval tests)
```
