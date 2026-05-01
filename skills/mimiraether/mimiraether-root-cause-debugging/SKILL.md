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

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too |
| "Emergency, no time for process" | Systematic is FASTER than guess-and-check |
| "Just try this first, then investigate" | First fix sets the pattern |
| "I'll write test after confirming fix works" | Untested fixes don't stick |
| "Multiple fixes at once saves time" | Can't isolate what worked |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause |

---

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, trace data | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, tests pass |

---

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
