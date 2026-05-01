# RalphLoop vs Hermes AgentLoop 对比分析

## 1. 根本差异

| 方面 | Hermes AgentLoop | RalphLoop |
|------|----------------|-----------|
| **核心任务** | Agent多轮对话 + 工具调用 | Skill代码块执行 + 验证 |
| **循环驱动** | LLM API响应（tool_calls） | 本地执行（subprocess） |
| **上下文** | 对话历史 + 工具结果 | 代码块列表 + 边界测试 |
| **终止条件** | finished_naturally / max_turns | consecutive_passed >= required |

---

## 2. Hermes关键设计可借鉴点

### 2.1 ToolError数据结构（可迁移）

Hermes的ToolError记录：
```python
@dataclass
class ToolError:
    turn: int
    tool_name: str
    arguments: str
    error: str
    tool_result: str
```

**RalphLoop现状**：问题只是字符串列表，没有结构化。

**迁移方案**：RalphLoop可以创建类似的`RalphError`结构：
```python
@dataclass
class RalphError:
    round_num: int
    block_index: int
    error_type: str  # SyntaxError, TimeoutError, RuntimeError等
    error_msg: str
    traceback: str
```

### 2.2 AgentResult结果封装（可迁移）

Hermes的AgentResult包含：
- messages: 完整历史
- turns_used: LLM调用次数
- finished_naturally: 是否自然结束
- reasoning_per_turn: 每轮推理
- tool_errors: 错误列表

**RalphLoop现状**：返回bool（成功/失败），没有结构化结果。

**迁移方案**：RalphLoop返回结构化结果：
```python
@dataclass
class RalphResult:
    success: bool
    rounds_completed: int
    consecutive_passed: int
    errors: List[RalphError]
    execution_time_ms: float
```

### 2.3 reasoning_per_turn（不适用）

RalphLoop不涉及LLM推理，不需要此机制。

### 2.4 线程池管理（可参考）

Hermes使用128 workers的ThreadPoolExecutor避免asyncio.run()死锁。

**RalphLoop现状**：使用subprocess.run()顺序执行代码块。

**改进可能**：使用ThreadPoolExecutor并行执行多个代码块。

---

## 3. RalphLoop独特优势

| 优势 | 说明 |
|------|------|
| **边界测试** | _test_boundary_cases检查空except、无break循环等 |
| **输出稳定性** | _check_output_stability验证无Error标记 |
| **自动修复建议** | _generate_fix根据问题类型生成修复方案 |
| **报告生成** | _save_report生成JSON格式锤炼报告 |

这些是Hermes没有的，RalphLoop的独特设计。

---

## 4. 进化计划

### Phase 1: 添加RalphError结构化错误（高优先级）

当前问题：
```python
round_result.problems.append(f"语法错误: {syntax_error}")
```

改进后：
```python
@dataclass
class RalphError:
    round_num: int
    block_index: Optional[int]
    category: str  # syntax, execution, boundary, timeout
    error_type: str
    error_msg: str
    fix_suggestion: str
```

### Phase 2: 添加RalphResult返回结构（中优先级）

当前：
```python
def run(self) -> bool:
    return self.consecutive_passed >= self.config.required_consecutive
```

改进后：
```python
@dataclass
class RalphResult:
    success: bool
    rounds_completed: int
    consecutive_passed: int
    errors: List[RalphError]
    total_execution_time_ms: float
    skill_path: str
    timestamp: str

def run(self) -> RalphResult:
    ...
    return RalphResult(
        success=self.consecutive_passed >= self.config.required_consecutive,
        rounds_completed=self.round_num,
        consecutive_passed=self.consecutive_passed,
        errors=self.errors,
        total_execution_time_ms=total_time,
        skill_path=self.config.skill_path,
        timestamp=datetime.now().isoformat()
    )
```

### Phase 3: 并行代码块执行（低优先级）

当前顺序执行：
```python
for i, code in enumerate(code_blocks):
    exec(code, {"__name__": "__sandbox__"})
```

可改进为：
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(exec_block, code) for code in code_blocks]
    results = [f.result() for f in futures]
```

---

## 5. 实施记录

| 日期 | 阶段 | 改动 | 状态 |
|------|------|------|------|
| 2026-04-24 | Phase 1 | 添加RalphError结构化错误 | ✅ |
| 2026-04-24 | Phase 2 | 添加RalphResult返回结构 | ✅ |
