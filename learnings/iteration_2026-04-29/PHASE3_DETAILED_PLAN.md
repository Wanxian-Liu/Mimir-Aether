# Phase 3: MimirAetherAgent 重构详细计划

> 基于 Ralph 5轮迭代的结果输出
> 执行时间: 2026-04-29
> 代码基准: `agent/core_loop.py` (2775行)

---

## R1: 沙盒验证当前状态

### 当前结构分析

| 指标 | 数值 |
|------|------|
| 文件总行数 | 2775 |
| MimirAetherAgent 类行数 | ~2351 (行268-2622) |
| 独立函数 | 3个 (skill_view_func, skills_list_func, skill_manage_func) |
| 方法总数 | 63个 |
| 数据类数量 | 9个 (MessageRole, Message, ToolCall, ToolResult, ToolError, ExecutionMetadata, Plan, ExecutionResult, ToolRegistry) |

### 现有模块依赖图

```
core_loop.py
├── .agent_loop.MimirAgentLoop        [已提取! 15137行] ← 重大
├── .async_bridge                     [已存在]
├── .context_compressor               [已存在]
├── .recovery                         [已存在]
├── .iteration_budget                 [已存在]
├── .credential_pool                  [已存在]
├── .prompt_builder                   [已存在]
├── .model_metadata                   [已存在]
├── .anthropic_adapter               [已存在]
├── .insights                        [已存在]
└── tools.registry                   [已存在]
```

### 关键发现

1. **MimirAgentLoop 已提取** — `agent_loop.py` 包含 `MimirAgentLoop`，这是从 `run_conversation()` 提取的执行引擎
2. **core_loop.py 仍然包含** — `MimirAetherAgent` 类（配置层）+ `MimirAgentLoop` 的导入使用
3. **数据类散落** — `ToolError`, `AgentResult` 等在 `core_loop.py` 和 `agent_loop.py` 都有定义（重复！）
4. **API 调用方法** — `_call_anthropic_api`, `_stream_openai_compatible` 可提取
5. **工具执行** — `_execute_tools`, `_execute_single_tool` 可提取
6. **凭证管理** — 已依赖 `credential_pool.py`，但 API key 解析逻辑仍在 `core_loop.py`
7. **独立函数底部** — `skill_view_func`, `skills_list_func`, `skill_manage_func` (行2622-2775) 可移至 `skill_funcs.py`

---

## R2: 模块依赖关系分析

### 依赖关系矩阵

```
模块                    | 依赖 core_loop.py | 依赖其他模块
------------------------|-------------------|--------------
agent_loop.MimirAgentLoop| ✓ (导入使用)      | async_bridge, dataclasses
message_handler         | ✗                 | dataclasses, Message (types)
tool_executor           | ✗                 | async_bridge, credential_pool
api_client              | ✗                 | anthropic_adapter, credential_pool
state_manager           | ✗                 | iteration_budget, recovery
skill_funcs             | ✗                 | skills_hub
types                   | ✗ (纯数据类)       | enum
```

### 内部依赖 (MimirAetherAgent 内部方法分组)

| 组 | 方法 | 行范围 | 提取优先级 |
|----|------|--------|-----------|
| **API 配置** | `_get_api_key`, `_get_model_base_url`, `_resolve_api_config` | 607-675 | P2 |
| **凭证初始化** | `_init_credential_pool` | 484-518 | P2 |
| **回调发射** | `_emit_status`, `_emit_interim_assistant`, `_fire_stream_delta` | 451-770 | P1 |
| **中断控制** | `interrupt`, `clear_interrupt`, `is_interrupted` | 773-792 | P1 |
| **系统提示** | `_build_system_prompt`, `_default_system_prompt` | 677-1119 | P2 |
| **工具注册** | `_register_builtin_tools` | 703-748 | P1 |
| **思考块处理** | `_strip_think_blocks`, `_extract_reasoning_from_response` | 798-861 | P2 |
| **工具调用去重/修复** | `_deduplicate_tool_calls`, `_repair_tool_call` | 863-917 | P1 |
| **消息构建** | `_build_full_messages`, `_needs_reasoning_propagation` | 1546-1613 | P1 |
| **模型调用** | `_call_model_with_tokens`, `_call_anthropic_api`, `_stream_openai_compatible` | 946-1899 | P2 |
| **工具执行** | `_execute_tools`, `_execute_single_tool` | 1890-2235 | P1 |
| **错误恢复** | `get_budget_warning`, `get_recovery_stats`, `check_and_warn_budget`, `handle_error_with_recovery`, `_recovery_error_handler` | 519-597 | P2 |
| **会话管理** | `_start_trajectory`, `_save_trajectory`, `_restore_session` | 2348-2513 | P2 |
| **技能管理** | `register_skill`, `get_skill_stats`, `list_skills`, `execute_skill`, `evolve_skill` | 2242-2283 | P2 |
| **Hook 系统** | `_invoke_hook`, `register_hook` | 2520-2558 | P2 |
| **备用/恢复** | `_try_activate_fallback`, `_restore_primary_runtime` | 2560-2620 | P3 |
| **工具辅助** | `_cleanup_aiohttp_connections` | 919-944 | P3 |
| **历史截断** | `_truncate_history` | 599-605 | P3 |
| **工具函数** | `_get_tool_name`, `_get_tool_arguments`, `_get_tool_id` | 185-214 | P1 (移到types) |
| **独立函数** | `skill_view_func`, `skills_list_func`, `skill_manage_func` | 2622-2775 | P1 |

---

## R3: 详细拆分计划

### 目标文件结构

```
agent/
├── core_loop.py              # 入口: MimirAetherAgent (~900行)
├── types.py                  # 数据类型 (~150行) [NEW]
├── message_handler.py        # 消息处理 (~400行) [NEW]
├── tool_executor.py          # 工具执行 (~450行) [NEW]
├── api_client.py             # API调用 (~350行) [NEW]
├── state_manager.py          # 状态管理 (~300行) [NEW]
├── skill_funcs.py            # 技能函数 (~150行) [NEW]
├── agent_loop.py             # 已存在: MimirAgentLoop (~1500行)
├── ...其他已有模块...
```

### 模块1: types.py [150行]

**职责**: 所有共享数据类型的唯一定义

**内容**:
```python
class MessageRole(Enum): ...
@dataclass class Message: ...
@dataclass class ToolCall: ...
@dataclass class ToolResult: ...
@dataclass class ToolError: ...          # 从agent_loop.py复制，删除agent_loop.py中的重复定义
@dataclass class ExecutionMetadata: ...
@dataclass class Plan: ...
@dataclass class ExecutionResult: ...

# 工具调用格式工具函数
def _get_tool_name(tc: dict) -> str: ...
def _get_tool_arguments(tc: dict) -> str: ...
def _get_tool_id(tc: dict) -> str: ...
```

**行数目标**: 150行
**导入方**: core_loop.py, agent_loop.py, tool_executor.py, message_handler.py

---

### 模块2: skill_funcs.py [150行]

**职责**: 独立技能查看/列表/管理函数

**内容** (从 core_loop.py 行 2622-2775 提取):
```python
def skill_view_func(name: str, file_path: str = None) -> str: ...
def skills_list_func(category: str = None) -> str: ...
def skill_manage_func(skill_name: str = None, action: str = None, ...) -> str: ...
```

**行数目标**: 150行
**导入方**: core_loop.py (原位导入，函数保持可用性)

---

### 模块3: message_handler.py [400行]

**职责**: 消息构建和推理传播

**内容**:
```python
class MessageHandler:
    def __init__(self, agent):  # 持有agent引用或传入必要依赖
        self.agent = agent

    def build_full_messages(self) -> List[Dict]: ...
    def needs_reasoning_propagation(self) -> bool: ...
    def strip_think_blocks(self, content: str) -> str: ...
    def extract_reasoning_from_response(self, response: Dict) -> Optional[str]: ...
    def deduplicate_tool_calls(self, tool_calls: list) -> list: ...
    def build_system_prompt(self) -> str: ...
    def default_system_prompt(self) -> str: ...
```

**行数目标**: 400行
**导入方**: core_loop.py (MimirAetherAgent)

---

### 模块4: tool_executor.py [450行]

**职责**: 工具调用的调度和执行

**内容**:
```python
class ToolExecutor:
    def __init__(self, agent): ...

    async def execute_tools(self, tool_calls: List[Dict], turn: int = 0) -> List[ToolResult]: ...
    async def execute_single_tool(self, tool_call: Dict, turn: int = 0) -> ToolResult: ...
    async def cleanup_aiohttp_connections(self, session) -> int: ...
    def repair_tool_call(self, tool_name: str) -> str | None: ...
    async def _execute_with_semaphore(self, tool_call: Dict) -> ToolResult: ...
```

**行数目标**: 450行
**导入方**: core_loop.py (MimirAetherAgent)

---

### 模块5: api_client.py [350行]

**职责**: API 调用封装

**内容**:
```python
class APIClient:
    def __init__(self, agent): ...

    async def call_model_with_tokens(self, messages: List[Dict], ...) -> Tuple[Dict, float]: ...
    async def call_anthropic_api(self, messages: List[Dict], ...) -> Dict: ...
    async def stream_openai_compatible(self, messages: List[Dict], ...) -> Dict: ...
    def get_api_key(self) -> str: ...
    def get_model_base_url(self) -> str: ...
    def resolve_api_config(self, model_name: str = None) -> Dict[str, Any]: ...
    def init_credential_pool(self) -> None: ...
```

**行数目标**: 350行
**导入方**: core_loop.py (MimirAetherAgent)

---

### 模块6: state_manager.py [300行]

**职责**: 状态管理、会话、轨迹、Hook

**内容**:
```python
class StateManager:
    def __init__(self, agent): ...

    # 中断控制
    def interrupt(self, message: str = None) -> None: ...
    def clear_interrupt(self) -> None: ...
    def is_interrupted(self) -> bool: ...

    # 回调发射
    def emit_status(self, message: str) -> None: ...
    def emit_interim_assistant(self, content: str) -> None: ...
    def fire_stream_delta(self, text: str) -> None: ...
    def has_stream_consumers(self) -> bool: ...

    # 轨迹
    def start_trajectory(self): ...
    def save_trajectory(self, completed: bool): ...
    def restore_session(self, session_id: str = None) -> bool: ...

    # Hooks
    def invoke_hook(self, hook_name: str, **kwargs) -> List[Any]: ...
    def register_hook(self, hook_name: str, hook_func: callable) -> None: ...

    # 历史管理
    async def truncate_history(self, keep_recent: int = 10) -> None: ...
```

**行数目标**: 300行
**导入方**: core_loop.py (MimirAetherAgent)

---

### 核心: core_loop.py 精简至 ~900行

**剩余内容**:
1. 所有 `from ... import ...` 语句
2. `ToolRegistry` 类 (兼容层, 231-265)
3. `MimirAetherAgent` 类:
   - `__init__` (初始化所有子模块)
   - `chat()` - 入口
   - `run_conversation()` - 主循环 (使用 `MimirAgentLoop`)
   - `register_builtin_tools()` - 工具注册 (调用 `agent_loop` 的注册逻辑)
   - `reset()` - 重置
   - `build_system_prompt()` - 代理方法
   - `execute_skill()`, `evolve_skill()` - 技能管理代理
   - `register_skill()`, `get_skill_stats()`, `list_skills()` - 技能管理代理
   - `get_budget_warning()`, `get_recovery_stats()` - 预算/恢复代理
   - `check_and_warn_budget()`, `handle_error_with_recovery()` - 错误处理代理
   - `_try_activate_fallback()`, `_restore_primary_runtime()` - 备用代理

**行数目标**: ~900行（不含空行和注释）

---

## R4: 风险评估

### 风险矩阵

| 步骤 | 操作 | 风险等级 | 影响 | 缓解措施 | 回滚方案 |
|------|------|---------|------|---------|---------|
| 1 | types.py 提取 | 🟡 中 | 编译失败 | 先导出相同符号，保持向后兼容 | 立即撤销 |
| 2 | skill_funcs.py 提取 | 🟢 低 | 函数找不到 | 旧位置保留 import 桥接 | 删除新文件 |
| 3 | message_handler.py 提取 | 🟡 中 | 消息格式变化 | 端到端测试 | 恢复方法到原位 |
| 4 | tool_executor.py 提取 | 🔴 高 | 工具执行崩溃 | mock 测试 | 保留原方法作为 fallback |
| 5 | api_client.py 提取 | 🔴 高 | API 调用失败 | 隔离测试 | 保留原方法作为 fallback |
| 6 | state_manager.py 提取 | 🟡 中 | 状态丢失 | 保存点测试 | 恢复方法到原位 |
| 7 | core_loop.py 最终清理 | 🟡 中 | 循环引用 | 延迟导入 | 恢复 import |

### 最危险步骤分析

**步骤4&5 (tool_executor & api_client)**:
- 涉及异步执行、并发控制
- 依赖 `agent._xxx` 状态变量
- 缓解: 注入依赖而非直接引用 agent 实例

---

## R5: 执行计划

### 分步骤执行顺序

```
[Step 0] 备份与准备
  ├── 创建备份: cp core_loop.py core_loop.py.backup_20260429
  ├── 创建目标目录: mkdir -p agent/refactor_backup/
  └── 验证当前测试通过: pytest agent/test_agent_loop.py -v

[Step 1] types.py 提取 (最小风险)
  ├── 创建 agent/types.py
  ├── 导入所有数据类和工具函数
  ├── core_loop.py: from .types import * (向后兼容)
  ├── agent_loop.py: 删除重复的 ToolError/AgentResult 定义
  └── 验证: python -c "from agent.types import Message, ToolCall"

[Step 2] skill_funcs.py 提取 (独立函数)
  ├── 创建 agent/skill_funcs.py
  ├── 从 core_loop.py 删除 skill_view_func, skills_list_func, skill_manage_func
  ├── core_loop.py: from .skill_funcs import * (向后兼容)
  └── 验证: python -c "from agent.skill_funcs import skill_view_func"

[Step 3] message_handler.py 提取
  ├── 创建 agent/message_handler.py
  ├── 提取 _build_full_messages, _needs_reasoning_propagation, _strip_think_blocks,
  │        _extract_reasoning_from_response, _deduplicate_tool_calls,
  │        _build_system_prompt, _default_system_prompt
  ├── core_loop.py 改为: self.message_handler = MessageHandler(self)
  ├── 代理方法调用: return self.message_handler.build_full_messages()
  └── 验证: pytest agent/test_agent_loop.py::TestMessageHandler -v

[Step 4] tool_executor.py 提取 (高风险)
  ├── 创建 agent/tool_executor.py
  ├── 提取 _execute_tools, _execute_single_tool, _cleanup_aiohttp_connections, _repair_tool_call
  ├── 注入依赖: def __init__(self, registry, credential_pool, ...): 不依赖整个agent
  ├── core_loop.py: self.tool_executor = ToolExecutor(
  │       registry=self.tool_registry, credential_pool=self.credential_pool, ...)
  ├── 保留原方法作为 fallback (带 # DEPRECATED 注释)
  └── 验证: pytest agent/test_agent_loop.py::TestToolExecutor -v

[Step 5] api_client.py 提取 (高风险)
  ├── 创建 agent/api_client.py
  ├── 提取 _call_model_with_tokens, _call_anthropic_api, _stream_openai_compatible,
  │        _get_api_key, _get_model_base_url, _resolve_api_config, _init_credential_pool
  ├── 注入依赖: 不直接引用agent内部状态
  ├── core_loop.py: self.api_client = APIClient(...)
  ├── 保留原方法作为 fallback
  └── 验证: pytest agent/test_agent_loop.py::TestAPIClient -v

[Step 6] state_manager.py 提取
  ├── 创建 agent/state_manager.py
  ├── 提取所有中断/回调/轨迹/hook/truncate 相关方法
  ├── core_loop.py: self.state_manager = StateManager(self)
  └── 验证: pytest agent/test_agent_loop.py::TestStateManager -v

[Step 7] core_loop.py 最终清理
  ├── 删除所有已迁移方法（保留代理方法）
  ├── 删除保留的 fallback 方法（确认无引用）
  ├── 整理 import 语句
  └── 验证: python -c "from agent.core_loop import MimirAetherAgent"

[Step 8] 端到端测试
  ├── pytest agent/test_agent_loop.py -v
  ├── pytest agent/test_integration.py -v
  └── 手动测试: python -m agent.core_loop (如果可行)
```

### 里程碑定义

| 里程碑 | 验收标准 | 目标行数 |
|--------|---------|---------|
| M1: 类型系统独立 | `from agent.types import Message, ToolCall, ToolError` 正常 | core_loop: 2625 |
| M2: 技能函数独立 | skill_view_func 等3个函数在新文件正常工作 | core_loop: 2545 |
| M3: 消息处理独立 | 对话流程中消息构建正常 | core_loop: 2145 |
| M4: 工具执行独立 | 工具调用（exec/read/write等）正常 | core_loop: 1695 |
| M5: API客户端独立 | 模型调用（DeepSeek/MiniMax等）正常 | core_loop: 1345 |
| M6: 状态管理独立 | 中断/回调/轨迹/hook 正常 | core_loop: 1045 |
| **M7: 重构完成** | core_loop.py ≤ 900行，所有测试通过 | core_loop: ≤ 900 |

### 每步骤验证方法

```bash
# 通用验证脚本
python -c "
    from agent.core_loop import MimirAetherAgent
    from agent.types import Message, ToolCall, ToolResult, ToolError
    from agent.skill_funcs import skill_view_func, skills_list_func, skill_manage_func
    print('✅ Import test passed')
"

# 模块验证
pytest agent/test_agent_loop.py -v --tb=short

# 行数验证
wc -l agent/core_loop.py  # 应该递减
```

---

## 数据流图

```
用户输入
    ↓
MimirAetherAgent.run_conversation()
    ├─ state_manager.check_interrupted()     [state_manager.py]
    ├─ message_handler.build_full_messages() [message_handler.py]
    ├─ api_client.call_model()              [api_client.py]
    │   ├─ api_client._stream_openai_compatible()
    │   └─ api_client._call_anthropic_api()
    ├─ message_handler.extract_reasoning()   [message_handler.py]
    ├─ tool_executor.execute_tools()         [tool_executor.py]
    │   └─ tools.registry.dispatch()
    ├─ message_handler.deduplicate_tool_calls() [message_handler.py]
    ├─ state_manager.emit_interim()         [state_manager.py]
    ├─ state_manager.save_trajectory()       [state_manager.py]
    └─ 循环或返回
```

---

## 依赖注入设计 (关键)

为避免循环引用，所有子模块使用**依赖注入**而非直接引用 agent：

```python
# ❌ 旧设计 (循环引用风险)
class MessageHandler:
    def __init__(self, agent):
        self.agent = agent  # 强引用

# ✅ 新设计 (依赖注入)
class MessageHandler:
    def __init__(self, config: MessageHandlerConfig):
        self.config = config
        self._build_system_prompt = config.build_system_prompt_fn
```

具体依赖:

| 子模块 | 需要注入的依赖 |
|--------|---------------|
| MessageHandler | system_prompt_fn, model_config, callbacks |
| ToolExecutor | registry, credential_pool, callbacks, aiohttp_session |
| APIClient | api_key_fn, base_url_fn, credential_pool, callbacks |
| StateManager | callbacks, interrupt_flag, trajectory_dir |

---

## 附录: 已知问题

### 问题1: ToolError/AgentResult 重复定义
- `core_loop.py` 行130定义 `ToolError`
- `agent_loop.py` 行38也定义 `ToolError`
- **解决**: 统一到 `types.py`，两个文件都导入

### 问题2: MimirAgentLoop 已从 run_conversation 提取
- `run_conversation()` 方法(行1130-1535) 实际上调用了 `MimirAgentLoop`
- 但 `MimirAetherAgent.__init__` 中仍有很多配置逻辑
- **解决**: 让 `MimirAetherAgent` 作为配置层，`MimirAgentLoop` 作为执行层

### 问题3: 残留死代码
- `skill_funcs` 相关代码 (~150行) 已不再被 MimirAetherAgent 使用
- 但模块级函数 `skill_view_func` 等仍定义在文件末尾
- **解决**: 提取到 `skill_funcs.py`，保持向后兼容
