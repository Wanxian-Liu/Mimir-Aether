---
name: mimiraether-root-cause-debugging
description: Systematic debugging approach with 4-phase root cause investigation — NO fixes without understanding the problem first. Inspired by Hermes Agent's systematic-debugging skill.
version: 1.0.0
author: MimirAether (learned from Hermes Agent)
license: MIT
metadata:
  hermes:
    tags: [debugging, troubleshooting, root-cause, investigation, problem-solving]
    related_skills: [test-driven-development, mimiraether-plan-mode]
    learned_from: hermes-agent/systematic-debugging
---

# Root Cause Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**The Iron Law:**
```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

## The Four Phases

Complete each phase before proceeding to the next.

---

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes

**Action:** Use `read_file` on the relevant source files.

### 2. Reproduce Consistently

- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, don't guess

**Action:** Run the failing test or trigger the bug:

```bash
# Run specific failing test
pytest tests/test_module.py::test_name -v

# Run with verbose output
pytest tests/test_module.py -v --tb=long
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 4. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Data flow traced to origin
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form a Single Hypothesis

- State clearly: "I think X is the root cause because Y"
- Write it down
- Be specific, not vague

### 2. Test Minimally

- Make the SMALLEST possible change to test the hypothesis
- One variable at a time
- Don't fix multiple things at once

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### 4. If Fix Doesn't Work — The Rule of Three

**Count: How many fixes have you tried?**

- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture**

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling
- Fixes require "massive refactoring"
- Each fix creates new symptoms elsewhere

**STOP and discuss with user before attempting more fixes.**

---

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

---

## Anti-Rationalization Table

| LLM 常用借口 | 为什么是错的 | 正确行动 |
|:------------|:-----------|:---------|
| "问题很简单，不用走流程" | 简单问题也有根因。跳过流程=重新经历15轮蒸馏循环 | 必须完成 Phase 1（读错误→复现→查更改→追踪数据流）|
| "紧急，没时间走流程" | 系统化走流程比试错法更快。紧急时最需要纪律 | 走 Phase 1 精简版：读错误→复现→查更改 |
| "我先试这个，不行再查" | 第一个修复设定了模式盲区。先试的往往是错的 | 先完成 Phase 1，再形成假设 |
| "确认修好了再写测试" | 没测试的修复=没验证。我说"修好了"但盘上没变，这就是16轮蒸馏失败的模式 | 先写回归测试再现 bug，再修复 |
| "一次修多个，省时间" | 无法隔离哪个修复有效。多个同时修=不知道修没修好 | 一次只修一个，修完验证再修下一个 |
| "我看到问题了，我直接修" | 看到症状≠理解根因。症状在 Line 447，根因可能在 Line 72 | 读完完整函数（至少完整读完）再动 |
| "之前修过类似的，这次也一样" | 蒸馏 `***` 字面量和 `os.replace` 跳过是两个完全不同的根因 | 每次重新做 Phase 1 数据流追踪 |
| "已经修了3次了，再试一次" | 规则上限：≥3次失败=架构问题。再修一次=第4次失败 | STOP——读文档重审设计，与用户讨论 |
| "看输出就行了，不用读盘" | 终端输出"写入成功"≠盘上数据变了。这是16轮蒸馏失败的根因 | 任何写操作后必须 `read_file` 或 `json.load` 验证盘上数据 |
| "我试过了，它做不到" | pi -p 测试不带 `--provider/--model` 就下"不加载扩展=架构级障碍"的结论，被刘哥用完整命令实测推翻（带参数后 team 工具全部加载）。测试环境/参数不同=结论不可比 | 下"不可能/不支持"结论前，必须用与用户**完全相同的命令**（含全部参数、环境变量、工作目录）复现；无法复现就先复现，再下结论 |

---

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, trace data | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, tests pass |

---

## Critical: `***` Literal Bug Pattern

**症状：** API call 始终 401，但 .env / /proc/environ / config.yaml 中的 key 都是正确的。

**根因：** Python 源文件中关键位置出现了字面 `***` 字符。这两个 `***` 不是模板替换——是文件内容真实的三颗星号。具体位置：
1. `_DREAM_MAX_TOKENS=***` — 应为 `_DREAM_MAX_TOKENS = 4096`（整数），`***` 字面量会让 max_tokens 传空字符串给 API
2. `entry.startswith(b"DEEPSEEK_API_KEY=***")` — 应为 `startswith(b"DEEPSEEK_API_KEY=")`，`***` 字面量会让 /proc key 注入永不匹配真实的 `sk-...` key

**排查方法：** `python3 -c "with open('file.py', 'rb') as f: lines = f.readlines(); print(repr(lines[N-1]))"` — 用二进制模式读文件确认真实内容。`read_file` 不会显示 `***` 不是替换而是字面量。

**为什么之前的修复都无效：** 每次修的是外圈（provider_registry fallback、/proc 扫描路径、cron 脚本调用方式、asyncio.run），从未触达文件中的字面 `***`。最内层的 bug 被所有外层修复掩盖了。

## Debugging Patterns Reference

### Pattern: Null Pointer After API Call
```
Phase 1: Trace where null originates
Phase 2: Compare with working API call patterns
Phase 3: Hypothesis: API returning empty body when error occurs
Phase 4: Add null check + error logging, add regression test
```

### Pattern: Intermittent Test Failure
```
Phase 1: Reproduce with verbose output, check timing
Phase 2: Look for async/parallel execution differences
Phase 3: Hypothesis: Race condition on shared state
Phase 4: Add locks, test with stress runs
```

### Pattern: Performance Regression
```
Phase 1: Profile to find slow function, check recent changes
Phase 2: Compare with previous performance data
Phase 3: Hypothesis: New query without index
Phase 4: Add index, benchmark before/after
```

---

## Auto-Retry and Recovery Strategies

### When to Retry

**Retry immediately for:**
- Transient network failures (timeout, connection refused)
- Temporary resource exhaustion (memory pressure, rate limits)
- Service unavailability (restarting, overloaded)

**DO NOT retry for:**
- Authentication/authorization failures (won't fix itself)
- Invalid input/parameters (will fail again)
- Resource not found (404) unless source is unreliable
- Business logic errors (bug in code)
- Data corruption

### Retry Strategy: Exponential Backoff

```python
import time
import random

def retry_with_backoff(func, max_retries=3, base_delay=1, max_delay=30):
    """Exponential backoff with jitter - prevents thundering herd."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (NetworkError, TimeoutError, ServiceUnavailable) as e:
            if attempt >= max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # 0-10% jitter
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay + jitter:.1f}s...")
            time.sleep(delay + jitter)
```

### Circuit Breaker Pattern

**Prevents cascading failures by stopping repeated attempts after threshold:**

```python
class CircuitBreaker:
    CLOSED = "closed"  # Normal operation
    OPEN = "open"       # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = self.CLOSED
        self.failures = 0
        self.last_failure_time = None
    
    def call(self, func):
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = self.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is OPEN")
        
        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failures = 0
        self.state = self.CLOSED
    
    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = self.OPEN
```

### Fallback Strategies

**Provide degraded functionality when primary fails:**

| Scenario | Fallback Options |
|----------|-----------------|
| API timeout | Return cached data, use default value |
| Database unavailable | Read from replica, return stale data with warning |
| External service down | Use mock/stub, queue for later |
| Rate limited | Exponential backoff, prioritize critical paths |

```python
def get_user_data(user_id, use_cache=True):
    try:
        return api.get_user(user_id)
    except RateLimitError:
        if use_cache:
            return cache.get(f"user:{user_id}")
        raise  # Propagate if cache miss
    except ServiceUnavailable:
        # Return stale but usable data
        return cache.get_stale(f"user:{user_id}", max_age=3600)
```

### Recovery Checkpoints

**Save state periodically for recovery:**

```python
class RecoveryCheckpoint:
    def __init__(self, checkpoint_file):
        self.checkpoint_file = checkpoint_file
        self.state = self._load()
    
    def _load(self):
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file) as f:
                return json.load(f)
        return {"step": 0, "data": {}}
    
    def save(self, step, data):
        self.state = {"step": step, "data": data}
        with open(self.checkpoint_file, "w") as f:
            json.dump(self.state, f)
    
    def resume(self):
        return self.state.get("step", 0), self.state.get("data", {})
```

---

## Approval Mechanism

### When to Request Approval

**HIGH RISK operations require explicit approval:**

| Operation | Risk Level | Requires Approval |
|-----------|-----------|-------------------|
| Production database writes | CRITICAL | Always |
| `rm -rf` or destructive cleanup | CRITICAL | Always |
| Changing authentication/authorization | CRITICAL | Always |
| Deploying to production | HIGH | Always |
| Modifying system configuration | HIGH | Always |
| Deleting user data | HIGH | Always |
| External API calls (billing, users) | MEDIUM | For first time |
| Running tests on production | MEDIUM | Verify intent |
| Creating new resources | LOW | Batch acceptable |

### Approval Request Format

```
⚠️ APPROVAL REQUIRED

Action: [What will happen]
Risk: [CRITICAL/HIGH/MEDIUM/LOW]
Impact: [What breaks if wrong]
Rollback: [How to undo]

Options:
  [y] Yes, proceed
  [n] No, skip
  [s] Show me the exact changes
  [p] Proceed without asking again

> _
```

### Approval Categories

**CRITICAL (Explicit y/n required):**
- Database: DELETE, DROP, TRUNCATE, UPDATE without WHERE
- Files: `rm -rf`, destructive overwrites
- Security: Passwords, keys, permissions changes
- Production: Deployment, scaling, config changes

**HIGH (Confirm before proceeding):**
- Creating users/accounts
- Sending external communications
- Resource creation with cost implications
- Configuration changes

**MEDIUM (Warn and proceed if no objection):**
- Running long operations (>5 min)
- Batch operations affecting multiple items
- Non-destructive modifications

---

## Error Classification Quick Reference

| Error Type | Retry? | Fallback? | Approval? |
|------------|--------|-----------|-----------|
| Network timeout | ✓ Exponential backoff | ✓ Cache | ✗ |
| 401/403 Auth | ✗ Fix creds | ✗ | ✓ If config |
| 404 Not found | ✗ | ✓ Default | ✗ |
| 429 Rate limit | ✓ Long backoff | ✓ Queue | ✗ |
| 500 Server error | ✓ Limited retries | ✓ Degraded | ✗ |
| 503 Unavailable | ✓ Circuit breaker | ✓ Alternative | ✗ |
| Out of memory | ✗ | ✓ Reduce scope | ✓ Increase |
| Deadlock | ✗ Fix code | ✗ | ✓ If timeout |
| Data corruption | ✗ Fix source | ✗ | ✓ Restore |

---

## Integration with Plan Mode

When debugging complex issues:

1. **Use plan mode first** if fix requires multiple steps
2. **Document the recovery path** before starting
3. **Set checkpoints** for long operations
4. **Request approval** for high-risk steps
5. **Verify incrementally** after each phase

---

**Remember:** Systematic debugging takes discipline. The iron law exists because guessing "feels" faster but always costs more in the end.
