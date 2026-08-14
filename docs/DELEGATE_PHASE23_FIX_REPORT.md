# Pi(delegate_task) 习惯化根治 Phase 2+3 报告 — Mimir 执行

**日期**：2026-08-15（北京时间 2026-08-14 晚间执行）
**执行者**：MimirAether
**角色**：从库 `engineering/engineering-backend-architect.md` 查的 **Backend Architect**
**角色核心规则引用**：「Implement proper error handling, circuit breakers, and graceful degradation — Define timeout budgets, retry policies… for every external call」（角色卡 §Ensure System Reliability）。本次 L349 静默吞错→显式 raise 即 error handling 纪律的落地。
**任务来源**：刘哥派发（Hermes 前置审计精确位置），四方讨论共识 Phase 2+3（基础设施缺位的代码层修复）

---

## 一、改动清单（只改 2 个文件，边界内）

### tools/delegate_tool.py（Phase 2，3 处）

1. **新增异常类 `DelegateBaseUrlMissingError(RuntimeError)`**（L37-46）
   - 文件顶部 `VALID_REASONING_EFFORTS` 之后定义，带 docstring 说明背景。

2. **L349 静默 getattr → 显式 raise**（L358-368）
   - 原代码：`effective_base_url = override_base_url or getattr(parent_agent, "base_url", None)`
   - 新代码：`effective_base_url = ...` 后紧跟
     ```python
     if not effective_base_url:
         raise DelegateBaseUrlMissingError(
             "delegate_task: no base_url resolved (override_base_url not provided and "
             f"parent_agent has no base_url; parent type={type(parent_agent).__name__}). "
             "Child agents would silently fall back to the provider default URL, "
             "causing model/endpoint mismatch. ..."
         )
     ```
   - **效果**：base_url 缺失不再静默 → child 不再默默走默认 URL 模型错乱 → bug 可见。
   - **不影响正常路径**（已核实）：gateway 正常 parent 是 `AIAgent`（run_agent.py），构造时 `runtime_kwargs` 含 `base_url`（session_mixin.py L148）→ getattr 有值不 raise。仅 MimirAetherAgent（无 base_url 属性，core_loop.py 用 runtime dict）+ 未配置 delegation 时 raise——正是 068abfc 遗留的静默错误场景。

3. **L1033 description WHEN TO USE 量化触发**（L1053-1063）
   - 新增量化触发（对齐 AGENTS.md 粒度尺 + 默认委派口径）：
     - `ANY task decomposable into >=2 independent subtasks`
     - `>=3 same-pattern tasks (independent, same pattern)`
     - `Subtasks independent with no dependencies (parallel-safe)`
     - `Subtasks each >=30s and I/O-heavy`
   - WHEN NOT TO USE 新增：`Single-step small operations / total <60s -> do it directly`、`Strong dependency chains (subtasks NOT independent)`
   - 保留原有 reasoning-heavy 等条目。

### skills/skill_manager.py（Phase 3，1 处）

4. **L108 INFO → WARNING（条件化）**
   - 原：`logger.info(f"SkillManager initialized with {len(self.skills)} skills")`
   - 新：
     ```python
     skill_count = len(self.skills)
     if skill_count == 0:
         logger.warning("SkillManager initialized with 0 skills (skills asleep — check skills metadata)")
     else:
         logger.info(f"SkillManager initialized with {skill_count} skills")
     ```
   - **效果**：0 skills（技能沉睡/元数据加载失败）→ WARNING 可被发现；正常 >0 → 保持 INFO 不噪音。

## 二、cap 核实结果（任务第 3 点：盘上核实，不擅自改）

- **`tools/delegate_tool.py` L76：`_DEFAULT_MAX_CONCURRENT_CHILDREN = 3`** —— **生效值**。
  `_get_max_concurrent_children()`（L80-103）优先级：`config.yaml delegation.max_concurrent_children` > env `DELEGATION_MAX_CONCURRENT_CHILDREN` > **默认 3**。L696-704 用该值校验批量 tasks 数量，超限返回清晰 tool_error。
- **`agent/subagent.py` L64：`SubAgentPool.__init__(self, max_concurrent: int = 5)`** —— 这是 **SubAgentPool**（另一个组件：任务分解/子任务池，pi_crew_bridge 用），**不是 delegate_task 的批量并行 cap**。两者互不冲突。
- **结论**：Loki 说的"默认 3"**正确**——delegate_tool.py 有独立 cap=3 且生效。subagent.py 的 5 是不同组件的默认。**按任务指示未擅自修改**，仅报告。schema description（L1108）也写 default 3，口径一致。

## 三、验证输出（盘上证据）

### 1. ast 语法检查 ✅
```
OK: tools/delegate_tool.py
OK: skills/skill_manager.py
```

### 2. grep 确认改动落盘 ✅
```
L37: class DelegateBaseUrlMissingError(RuntimeError):
L363: raise DelegateBaseUrlMissingError(
L1054: "- ANY task decomposable into >=2 independent subtasks\n"
L1055: "- >=3 same-pattern tasks (independent, same pattern)\n"
L112: logger.warning("SkillManager initialized with 0 skills (skills asleep — check skills metadata)")
```

### 3. import 运行时测试 ✅
```
OK: import tools.delegate_tool
OK: DelegateBaseUrlMissingError raise/catch works: test
OK: schema description has '>=2 independent subtasks': True
OK: schema description has '>=3 same-pattern tasks': True
OK: import skills.skill_manager
OK: SkillManager(storage_dir=/tmp/...) instantiated, skills=0
```

### 4. WARNING 级别真实触发验证 ✅
```
WARNING: SkillManager initialized with 0 skills (skills asleep — check skills metadata)
OK: 0-skills 触发的是 WARNING 级别，'技能沉睡'可被发现
```

## 四、边界与备份

- 备份：`tools/delegate_tool.py.bak_phase23`、`skills/skill_manager.py.bak_phase23`（cp 完成）
- 未改其他任何文件（不动 subagent.py、config、schema cap 值）

## 五、摘帽检查

本次以 **Backend Architect**（engineering/engineering-backend-architect.md）角色执行：错误处理纪律（raise 可见化）、接口契约维护（schema description）、系统性核实（cap 多源对比）。任务完成，**角色已摘**——后续对话不延续该角色口吻。
