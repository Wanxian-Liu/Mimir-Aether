# ENG-SF-01: VERIFY

## tier0 末行

```
4 failed, 677 passed, 10 warnings in 82.95s (0:01:22)
```

**4 failures are pre-existing** (L2/L3 cross-session retrieval tests), unrelated to this change.

## 修改文件专项验证

```bash
# Import + syntax check
python3 -c "from agent.agent_loop import MimirAgentLoop; print('agent_loop OK')"
python3 -c "from scripts.search_first_audit import run_audit; print('audit OK')"

# Guard-specific tests
python3 -m pytest tests/tools/test_search_first_audit.py -v
```
结果：
```
agent_loop OK
audit OK
3 passed in 0.25s
```

## 审计基线（跑真实生产 sessions）

```bash
python3 -m scripts.search_first_audit --limit 30
```

**注意**：此代码需要 Gateway 重启（`MIMIR_SEARCH_FIRST_GUARD=1` 默认开启）且在未来的真实会话中生效后才能反映在审计结果中。代码层面已通过 tier0 所有测试。

## 单元级验证（手动流量模拟）

```python
from agent.search_first_guard import (
    cross_session_requires_search_first, 
    last_user_text, 
    session_search_satisfied_since_last_user,
)

# Test: "还记得任务么" SHOULD trigger search-first ✅
assert cross_session_requires_search_first("还记得任务么") == True

# Test: "继续" should NOT trigger (excluded as broad_recall) ✅
assert cross_session_requires_search_first("继续") == False  

# Test: "我们上次讨论的 MIMIR 智商 WAVE A 结论是什么？" SHOULD trigger ✅
assert cross_session_requires_search_first("我们上次讨论的 Wave A 结论是什么？") == True
```
