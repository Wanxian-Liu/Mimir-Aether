# ENG-EVO-01: 验证

## tier0

```
./run_ralph_tier0.sh
```

末行：

```
4 failed, 677 passed
```

4 项失败均为预存（L2/L3 跨会话检索测试），与本次改动无关。

## tier0 完整行

```
FAILED tests/agent/test_cross_session_retrieval_l2.py::test_prefetch_uses_objective_query
FAILED tests/agent/test_cross_session_retrieval_l2.py::test_query_falls_back_to_next_session
FAILED tests/agent/test_cross_session_retrieval_l3.py::test_build_with_rag_off_matches_l2_search_fn
FAILED tests/agent/test_cross_session_retrieval_l3.py::test_build_with_rag_on_merged_injection
4 failed, 677 passed, 10 warnings in 79.38s (0:01:19)
```

## 手动验证 log 输出

改动生效后，关闭一个带 degraded_tools 的 session，检查 agent.log：

```bash
grep 'evolution detail' ~/.mimiraether/logs/agent.log
```

之前为零行。改后应至少出现格式如下的 detail 行：

```
post_analysis evolution detail session_id=... target=... action=... error=no error detail
```

## 回归

`git diff` 仅改动 1 行（`post_close_analysis.py:168` `and r.error` → `if not r.success`），无范副作用。
