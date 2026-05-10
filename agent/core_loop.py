"""
# 进化进度:正在学习Hermes架构
MimirAether Agent Core Loop

学习自Hermes AIAgent架构,重新实现的核心Agent类。

核心功能:
- 主对话循环
- 工具调用处理
- 上下文管理
- 迭代预算控制

集成模块:
- prompt_builder: System Prompt构建
- model_metadata: 模型元数据管理
- anthropic_adapter: Anthropic API适配
"""

import asyncio
import json
import logging
import os
import threading
import uuid
import hashlib
from typing import List, Dict, Any, Optional, Callable, Union
from pathlib import Path

# 加载.env文件（如果存在），确保API key正确
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        # 如果没有dotenv，手动解析.env文件
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and not os.environ.get(key):
                            os.environ[key] = value

# 统一类型系统: 从 types.py 导入所有数据类型
from .types import (
    MessageRole,
    Message,
    ToolCall,
    ToolResult,
    ToolError,
    ExecutionMetadata,
    Plan,
    ExecutionResult,
    _get_tool_name,
    _get_tool_arguments,
    _get_tool_id,
)
# 技能函数: 从 skill_funcs.py 导入 (Phase 3 M2)
from .skill_funcs import (
    skill_view_func,
    skills_list_func,
    skill_manage_func,
    SKILL_TOOL_SCHEMAS,
    SKILL_MANAGE_SCHEMA,
)

# 新模块导入
from .context_compressor import ContextCompressor, CompressionResult, HermesStyleCompressor
from .insights import InsightsEngine, MetricType
from memory.fencing import MemoryFencer
from skills.skill_manager import SkillManager, SkillStatus

# 自我进化模块：多层次错误恢复 & 增强迭代预算
from .recovery import (
    MultiLevelRecovery, RecoveryContext, RecoveryStats, RecoveryLevel,
    get_recovery, set_recovery
)
from .iteration_budget import (
    EnhancedIterationBudget, BudgetWarning, BudgetStats, IterationRecord,
    get_global_budget, set_global_budget, IterationBudget  # 保留向后兼容
)

# 导入Hermes SessionDB用于数据持久化
import sys
from pathlib import Path

from mimir_constants import get_mimir_home

# 添加MimirAether路径(优先)
mimir_root = get_mimir_home()
mimir_path = str(mimir_root)
if mimir_path not in sys.path:
    sys.path.insert(0, mimir_path)

# 可选兼容：仅在显式开启且路径存在时才注入 hermes-agent 路径。
# 默认保持纯 MimirAether 自包含，避免隐式依赖外部仓库。
_enable_legacy_hermes_path = os.getenv("MIMIRAETHER_ENABLE_HERMES_PATH", "0") == "1"
_hermes_env = os.getenv("HERMES_AGENT_HOME", "").strip()
_hermes_root = (
    Path(_hermes_env).expanduser()
    if _hermes_env
    else (Path.home() / "hermes-agent")
)
if _enable_legacy_hermes_path and _hermes_root.exists():
    hermes_path = str(_hermes_root)
    if hermes_path not in sys.path:
        sys.path.append(hermes_path)

try:
    from mimcore.gateway.session import SessionDB
except ImportError:
    SessionDB = None

# 集成新模块
from . import prompt_builder
from . import model_metadata
from . import anthropic_adapter

# 集成凭证池模块
from . import credential_pool
from .credential_pool import CredentialPool, PooledCredential, create_credential
# Async bridge: persistent event loops for safe sync-tool dispatch.
# Imported from agent/async_bridge.py (Hermes pattern).
# _tool_executor, resize_tool_pool, get_tool_loop, get_worker_loop
from .async_bridge import (
    get_tool_executor,
    resize_tool_pool,
    get_tool_loop,
    get_worker_loop,
)
# Backward-compatible alias
_tool_executor = get_tool_executor()

# MimirAgentLoop: pure execution engine extracted from this class
from .agent_loop import MimirAgentLoop, AgentResult as LoopAgentResult, ToolError as LoopToolError
from .llm_port import LlmInvocationPort
from .tool_port import ToolInvocationPort
from .session_port import SessionDbClientFactory, SessionRestorePort
from .checkpoint_port import CheckpointPersistencePort
from .kernel_overrides import AgentKernelOverrides


logger = logging.getLogger(__name__)


def _parse_write_file_arguments_string(raw_args: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse of write_file arguments from a raw string.

    Used when ``json.loads(raw_args)`` fails. Order: strict JSON (again after
    ``\\\"`` unescape), regex path/content extraction, ``path|content`` split,
    legacy truncated-JSON suffix heuristic.
    """
    import re

    if not isinstance(raw_args, str) or not raw_args.strip():
        return None

    try:
        d = json.loads(raw_args)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass

    try:
        d = json.loads(raw_args.replace('\\"', '"'))
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass

    path_match = re.search(r'"path"\s*:\s*"([^"]*)"', raw_args)
    content_match = re.search(r'"content"\s*:\s*"(.*?)"(?:\s*[,}])', raw_args, re.DOTALL)
    if path_match:
        path_val = path_match.group(1)
        content_val = content_match.group(1) if content_match else ""
        # Unescape any JSON-escaped quotes in content
        content_val = content_val.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
        return {"path": path_val, "content": content_val}

    if "|" in raw_args:
        parts = raw_args.split("|", 1)
        return {"path": parts[0], "content": parts[1] if len(parts) > 1 else ""}

    try:
        fixed = raw_args.rstrip()
        if not fixed.endswith("}"):
            fixed = fixed + '"}}'
        d = json.loads(fixed)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass

    return None


# IterationBudget已移动到iteration_budget.py模块
# 保留此注释以保持向后兼容
# 新代码请使用: from .iteration_budget import EnhancedIterationBudget, get_global_budget
from .iteration_budget import IterationBudget




# ── 工具注册表已统一到 tools/registry.py（Hermes 模式） ──
# 本地 ToolRegistry 兼容层：委托到真正的 tools.registry.registry
# 新代码应直接使用 tools.registry.registry 而非此兼容层。
import tools.registry as _tool_registry_module


class ToolRegistry:
    """
    工具注册表（兼容层）

    委托到 tools.registry.registry，提供与旧代码兼容的接口。
    工具通过 tools/ 目录下的模块自动注册（builtin.py, mimircore_tool.py 等），
    不再需要在 agent 中手动注册。
    """

    def __init__(self):
        # 委托到真正的全局 registry（单例）
        self._real_registry = _tool_registry_module.registry

    def register(self, name: str, func: callable, schema: dict):
        """注册工具（委托到真正的 registry）"""
        self._real_registry.register(
            name=name,
            toolset="compat",
            schema={"name": name, "description": schema.get("description", f"Tool: {name}"),
                    "parameters": schema.get("parameters", {})},
            handler=lambda args, **kw: func(**args) if callable(func) else func(args),
        )

    async def execute(self, name: str, arguments: dict):
        """执行工具（委托到真正的 registry.dispatch）"""
        from tools.strategy import route_tool_call

        name, arguments, err = route_tool_call(name, arguments)
        if err:
            return json.dumps({"error": err, "type": "routing_error"})
        result_str = self._real_registry.dispatch(name, arguments)
        return result_str

    def list_tools(self):
        """列出所有工具"""
        return self._real_registry.get_all_tool_names()

    def get_schema(self, name: str):
        """获取工具 schema"""
        return self._real_registry.get_schema(name)


class _BuiltinLlmBackend:
    """Default LLM path: HTTP / Anthropic / OpenAI-compatible (see ``_builtin_call_model_with_tokens``)."""

    __slots__ = ("_agent",)

    def __init__(self, agent: "MimirAetherAgent") -> None:
        self._agent = agent

    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        return await self._agent._builtin_call_model_with_tokens(messages, session_id)


class _BuiltinToolBackend:
    """Default tool path: semaphore + timeouts + registry dispatch (see ``_builtin_execute_tools``)."""

    __slots__ = ("_agent",)

    def __init__(self, agent: "MimirAetherAgent") -> None:
        self._agent = agent

    async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0) -> List[ToolResult]:
        return await self._agent._builtin_execute_tools(tool_calls, turn)


class _BuiltinSessionDbFactory:
    """Default: construct ``SessionDB()`` when the class is importable; else ``None``."""

    __slots__ = ()

    def create_session_db(self) -> Optional[Any]:
        if SessionDB is None:
            return None
        try:
            return SessionDB()
        except Exception:
            return None


class _BuiltinCheckpointBackend:
    """Default: global ``CheckpointManager`` from ``checkpoint_manager.get_checkpoint_manager``."""

    __slots__ = ()

    def load_checkpoint(self, task_id: str) -> Optional[Any]:
        from checkpoint_manager import get_checkpoint_manager

        return get_checkpoint_manager().load_checkpoint(task_id)

    def save_checkpoint(
        self,
        task_id: str,
        state: Dict[str, Any],
        current_step: int = 0,
        next_action: str = "继续执行",
    ) -> bool:
        from checkpoint_manager import get_checkpoint_manager

        return get_checkpoint_manager().save_checkpoint(
            task_id, state, current_step, next_action
        )

    def clear_checkpoint(self, task_id: str) -> bool:
        from checkpoint_manager import get_checkpoint_manager

        return get_checkpoint_manager().clear_checkpoint(task_id)


class _BuiltinSessionRestore:
    """Default session restore: Hermes SessionDB → ``conversation_history``."""

    __slots__ = ("_agent",)

    def __init__(self, agent: "MimirAetherAgent") -> None:
        self._agent = agent

    def restore_after_init(self, session_id: Optional[str] = None) -> bool:
        return self._agent._builtin_restore_session(session_id)


class MimirAetherAgent:
    """
    MimirAether核心Agent类

    学习自Hermes AIAgent,重新实现的Agent主循环。

    核心接口:
    - chat(): 主聊天接口
    - run_conversation(): 完整对话流程
    - build_system_prompt(): 构建系统提示
    """

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        max_iterations: int = 90,
        platform: str = "cli",
        system_prompt: str = None,
        save_trajectories: bool = False,
        stream_callback: callable = None,
        # Callback系统(学习自Hermes)
        step_callback: callable = None,
        status_callback: callable = None,
        tool_start_callback: callable = None,
        tool_complete_callback: callable = None,
        tool_progress_callback: callable = None,
        thinking_callback: callable = None,
        reasoning_callback: callable = None,
        clarify_callback: callable = None,
        interim_assistant_callback: callable = None,
        tool_gen_callback: callable = None,
        # Fallback机制
        fallback_model: dict = None,
        llm_backend: Optional[LlmInvocationPort] = None,
        tool_backend: Optional[ToolInvocationPort] = None,
        session_backend: Optional[SessionRestorePort] = None,
        session_db_factory: Optional[SessionDbClientFactory] = None,
        checkpoint_backend: Optional[CheckpointPersistencePort] = None,
        kernel_overrides: Optional[AgentKernelOverrides] = None,
    ):
        """
        初始化MimirAether Agent

        Args:
            model: 使用的模型
            max_iterations: 最大迭代次数
            platform: 运行平台
            system_prompt: 系统提示
            save_trajectories: 是否保存轨迹
            stream_callback: 流式输出回调函数
            step_callback: 每步执行后的回调
            status_callback: 状态变化的回调
            tool_start_callback: 工具开始执行的回调
            tool_complete_callback: 工具完成执行的回调
            tool_progress_callback: 工具执行进度的回调
            thinking_callback: Thinking内容回调
            reasoning_callback: Reasoning内容回调
            clarify_callback: 用户交互回调
            interim_assistant_callback: 临时助手响应回调
            tool_gen_callback: 工具生成回调
            fallback_model: Fallback模型配置
            llm_backend: 可选；实现 :class:`~agent.llm_port.LlmInvocationPort` 则替代默认 HTTP 调用路径
            tool_backend: 可选；实现 :class:`~agent.tool_port.ToolInvocationPort` 则替代默认工具批处理路径
            session_backend: 可选；实现 :class:`~agent.session_port.SessionRestorePort` 则替代默认 SessionDB 恢复路径
            session_db_factory: 可选；实现 :class:`~agent.session_port.SessionDbClientFactory` 则统一 Insights 与内置恢复所用的 DB 客户端构造
            checkpoint_backend: 可选；实现 :class:`~agent.checkpoint_port.CheckpointPersistencePort` 则替代断点续传用的检查点存取
            kernel_overrides: 可选；一次性打包多个后端字段；各显式构造参数优先于 bundle 内同名字段
        """
        self.model = model
        self.max_iterations = max_iterations
        self.platform = platform
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.save_trajectories = save_trajectories

        # 流式输出回调
        self.stream_callback = stream_callback
        self._stream_needs_break = False  # 流式输出段落分隔标志
        self._current_streamed_text = ""  # 当前流式输出的累积文本

        # Callback系统(学习自Hermes)
        self.step_callback = step_callback
        self.status_callback = status_callback
        self.tool_start_callback = tool_start_callback
        self.tool_complete_callback = tool_complete_callback
        self.tool_progress_callback = tool_progress_callback
        self.thinking_callback = thinking_callback
        self.reasoning_callback = reasoning_callback
        self.clarify_callback = clarify_callback
        self.interim_assistant_callback = interim_assistant_callback
        self.tool_gen_callback = tool_gen_callback

        # Fallback机制
        self.fallback_model = fallback_model
        self._fallback_activated = False
        self._primary_model = model  # 保存主模型配置

        # Status callback(学习自Hermes _emit_status)
        self._status_message = ""  # 当前状态消息
        self.quiet_mode = False  # 安静模式标志

        # Plugin hooks(学习自Hermes)
        for hook_name in self.VALID_HOOKS:
            setattr(self, f"_{hook_name}_hooks", [])

        # 初始化组件
        # 增强版迭代预算控制器（学习自Hermes）
        self.budget = EnhancedIterationBudget(
            max_total=max_iterations,
            track_history=True,
            warning_threshold=0.3,
            critical_threshold=0.1,
        )
        self.tool_registry = ToolRegistry()
        
        # 多层次错误恢复器（学习自Hermes 4层恢复策略）
        self.recovery = MultiLevelRecovery(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            enable_degrade=True,
            enable_compress=True,
            enable_truncate=True,
        )
        
        self.conversation_history: List[Message] = []
        self.max_history_length = 100  # 对话历史最大长度,防止内存耗尽

        # 新模块初始化
        # Hermes风格压缩器
        self.compressor = HermesStyleCompressor(
            model=model,
            threshold_percent=0.85,
            protect_first_n=3,
            protect_last_n=6,
            tail_token_budget=4000,
        )

        ko = kernel_overrides
        eff_session_db_factory = session_db_factory
        if eff_session_db_factory is None and ko is not None:
            eff_session_db_factory = ko.session_db_factory

        self._session_db_factory: SessionDbClientFactory = (
            eff_session_db_factory if eff_session_db_factory is not None else _BuiltinSessionDbFactory()
        )
        _db = self._session_db_factory.create_session_db()
        self.insights = InsightsEngine(_db) if _db else InsightsEngine()

        # 初始化SkillManager(自进化核心)
        self.skill_manager = SkillManager()

        self.fencer = MemoryFencer()
        self.fencer.enable_tag_wrapping = False  # Disable XML wrapping - breaks API message format

        # 初始化凭证池(在使用_get_api_key之前)
        self._credential_pool: Optional[CredentialPool] = None
        self._init_credential_pool()

        # 初始化model_metadata获取context_length
        self._context_length = model_metadata.get_model_context_length(
            model=model,
            base_url=self._get_model_base_url(),
            api_key=self._get_api_key(),
        )

        try:
            self.compressor.update_model(
                model=model,
                context_length=int(self._context_length or 8000),
                base_url=self._get_model_base_url(),
                api_key=self._get_api_key(),
                provider="",
                api_mode="",
            )
        except Exception as _e:
            logger.debug("compressor.update_model at init skipped: %s", _e)

        # 初始化prompt_builder构建系统提示
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = self._build_system_prompt()

        # 轨迹记录
        self._trajectory: List[Dict] = []

        # 工具调用并发限制(最多同时执行5个工具)
        self._tool_semaphore = asyncio.Semaphore(5)

        # Hermes风格执行元数据(学习自Hermes)
        # 在run_conversation开始时初始化
        self._tool_errors: List[ToolError] = []
        self._reasoning_per_turn: List[Optional[str]] = []
        self._execution_metadata: Optional[ExecutionMetadata] = None
        self._current_turn: int = 0  # 当前轮次，用于ToolError记录

        # 中断机制(学习自Hermes)
        self._interrupt_requested = False
        self._interrupt_message = None
        self._execution_thread_id = threading.get_ident()

        # 注册内置工具
        self._register_builtin_tools()

        eff_llm = llm_backend
        if eff_llm is None and ko is not None:
            eff_llm = ko.llm_backend
        eff_tool = tool_backend
        if eff_tool is None and ko is not None:
            eff_tool = ko.tool_backend
        eff_session = session_backend
        if eff_session is None and ko is not None:
            eff_session = ko.session_backend
        eff_checkpoint = checkpoint_backend
        if eff_checkpoint is None and ko is not None:
            eff_checkpoint = ko.checkpoint_backend

        self._llm_backend: LlmInvocationPort = (
            eff_llm if eff_llm is not None else _BuiltinLlmBackend(self)
        )
        self._tool_backend: ToolInvocationPort = (
            eff_tool if eff_tool is not None else _BuiltinToolBackend(self)
        )
        self._session_backend: SessionRestorePort = (
            eff_session if eff_session is not None else _BuiltinSessionRestore(self)
        )
        self._checkpoint_backend: CheckpointPersistencePort = (
            eff_checkpoint if eff_checkpoint is not None else _BuiltinCheckpointBackend()
        )

        logger.info(f"MimirAether initialized with model: {model}, context_length: {self._context_length}")

        # 尝试从SessionDB恢复最近的session
        # 初始化跨会话记忆
        self._cross_memory = None
        self._cross_context = None
        self._init_cross_session()

        self._restore_session()

    def _init_cross_session(self):
        """Initialize cross-session memory on session start"""
        try:
            from .cross_session_memory import CrossSessionMemory
            self._cross_memory = CrossSessionMemory()
            self._cross_memory.load()
            self._cross_memory.begin_session()
            if hasattr(self._cross_memory, 'summary'):
                summary = self._cross_memory.summary()
                if summary:
                    self._cross_context = summary
                    logger.info(f'[CrossSession] Loaded context: {len(summary)} items')
        except Exception as e:
            logger.warning(f'[CrossSession] Init failed: {e}')
            self._cross_memory = None

    def _save_cross_session(self):
        """Save current session context to cross-session memory"""
        if not hasattr(self, '_cross_memory') or self._cross_memory is None:
            return
        try:
            import json
            pending = getattr(self, '_pending_tasks', [])
            decisions = getattr(self, '_key_decisions', [])
            self._cross_memory.save_context({
                'last_task': getattr(self, '_last_task', ''),
                'key_decisions': decisions,
                'pending_tasks': pending,
            })
            logger.info('[CrossSession] Context saved')
        except Exception as e:
            logger.warning(f'[CrossSession] Save failed: {e}')

    def _emit_status(self, message: str) -> None:
        """
        发送状态消息到status_callback

        学习自Hermes _emit_status:
        - 通过status_callback发送状态更新
        - 用于CLI/Gateway显示状态变化
        """
        self._status_message = message
        if self.status_callback:
            try:
                self.status_callback(message)
            except Exception as e:
                logger.warning(f"status_callback error: {e}")
        elif not self.quiet_mode:
            # 如果没有callback但不是quiet模式,打印状态
            print(f"\n📍 {message}")

    def _emit_interim_assistant(self, content: str) -> None:
        """
        发送临时助手响应(流式输出时的中间响应)

        学习自Hermes:
        - interim_assistant_callback用于流式输出中间内容
        - 允许在完整响应前显示部分内容
        """
        if self.interim_assistant_callback:
            try:
                self.interim_assistant_callback(content)
            except Exception as e:
                logger.warning(f"interim_assistant_callback error: {e}")


    def _init_credential_pool(self) -> None:
        """初始化凭证池"""
        # 收集可用凭证
        entries = []

        # 从环境变量加载 DeepSeek
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if deepseek_key:
            entries.append(create_credential("deepseek", deepseek_key, "DeepSeek Primary"))

        # 从环境变量加载 MiniMax
        minimax_key = os.environ.get("MINIMAX_API_KEY", "").strip()
        if minimax_key:
            entries.append(create_credential("minimax", minimax_key, "MiniMax Primary"))

        # 从环境变量加载 OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            entries.append(create_credential("openai", openai_key, "OpenAI Primary"))

        # 从环境变量加载 Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if anthropic_key:
            entries.append(create_credential("anthropic", anthropic_key, "Anthropic Primary"))

        if entries:
            self._credential_pool = CredentialPool(self.model, entries, strategy="round_robin")
            logger.info(f"Credential pool initialized with {len(entries)} entries")
        else:
            logger.debug("No credentials found for pool, using environment variables directly")

    # ============================================================================
    # 预算和恢复状态（学习自Hermes）
    # ============================================================================
    
    def get_budget_warning(self) -> str:
        """获取当前预算警告级别"""
        level = self.budget.get_warning_level()
        remaining = asyncio.run(self.budget.get_remaining())
        total = self.budget.max_total
        pct = remaining / total * 100
        return f"[{level.value.upper()}] {remaining}/{total} ({pct:.1f}% remaining)"
    
    def get_recovery_stats(self) -> str:
        """获取恢复统计"""
        return self.recovery.format_stats()
    
    async def check_and_warn_budget(self) -> bool:
        """
        检查预算并发出警告
        
        Returns:
            是否应该继续执行
        """
        if self.budget.should_warn():
            warning = self.get_budget_warning()
            logger.warning(f"Iteration budget warning: {warning}")
            if self.status_callback:
                await self._emit_status(f"⚠️ {warning}")
            return self.budget.is_safe_to_continue()
        return True
    
    async def handle_error_with_recovery(
        self,
        error: Exception,
        context: dict = None
    ) -> bool:
        """
        使用多层次恢复处理错误
        
        Args:
            error: 发生的错误
            context: 错误上下文
            
        Returns:
            是否恢复成功
        """
        error_ctx = RecoveryContext(
            error=error,
            error_type=type(error).__name__,
            metadata=context or {}
        )
        
        try:
            # 使用恢复器的with_recovery
            await self.recovery.with_recovery(
                lambda: None,  # 恢复操作在error_handler中处理
                error_handler=self._recovery_error_handler,
                context=error_ctx
            )
            return True
        except Exception as e:
            logger.error(f"Unrecoverable error: {e}")
            return False
    
    async def _recovery_error_handler(
        self, 
        error: Exception, 
        context: RecoveryContext
    ) -> None:
        """恢复错误处理器"""
        level = context.current_level
        logger.warning(f"Recovery at level {level.value}: {error}")
        
        if level == RecoveryLevel.COMPRESS:
            # 触发上下文压缩
            self.budget.stats.compression_triggered += 1
            self.compressor.mark_context_probed()
            await self._emit_status("🔄 Compressing context...")
            
        elif level == RecoveryLevel.TRUNCATE:
            # 强制截断历史
            await self._truncate_history()
            await self._emit_status("✂️ Truncating history...")
    
    async def _truncate_history(self, keep_recent: int = 10) -> None:
        """截断对话历史"""
        if len(self.conversation_history) > keep_recent:
            truncated = self.conversation_history[-keep_recent:]
            removed = len(self.conversation_history) - len(truncated)
            self.conversation_history = truncated
            logger.info(f"Truncated {removed} messages from history")

    def _get_api_key(self) -> str:
        """获取当前模型的API key"""
        # Moonshot/Kimi系列 使用MOONSHOT_API_KEY环境变量
        if self.model.startswith("kimi-k2") or self.model.startswith("moonshot"):
            return os.environ.get("MOONSHOT_API_KEY", "")

        # DeepSeek优先使用DEEPSEEK_API_KEY，fallback到OPENROUTER_API_KEY（用于OpenRouter上的DeepSeek模型）
        if "deepseek" in self.model.lower():
            return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")

        # 优先从凭证池获取
        if self._credential_pool:
            selected = self._credential_pool.current()
            if selected:
                return selected.runtime_api_key

        # fallback到环境变量
        model_lower = self.model.lower()
        if "deepseek" in model_lower:
            return os.environ.get("DEEPSEEK_API_KEY", "")
        elif "minimax" in model_lower:
            return os.environ.get("MINIMAX_API_KEY", "")
        elif "anthropic" in model_lower or "claude" in model_lower:
            return os.environ.get("ANTHROPIC_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
        elif "openai" in model_lower or "gpt" in model_lower:
            return os.environ.get("OPENAI_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
        else:
            return os.environ.get("DEEPSEEK_API_KEY", "")

    def _get_model_base_url(self) -> str:
        """获取当前模型的API base URL"""
        # Moonshot/Kimi系列 使用Moonshot API
        if self.model.startswith("kimi-k2") or self.model.startswith("moonshot"):
            return "https://api.moonshot.cn"  # 不要加/v1,会在API调用时拼接

        model_lower = self.model.lower()
        if "deepseek" in model_lower:
            return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        elif "minimax" in model_lower:
            return os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com")
        elif "anthropic" in model_lower or "claude" in model_lower:
            return os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        elif "openai" in model_lower or "gpt" in model_lower:
            return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        else:
            return "https://api.deepseek.com"

    def _resolve_api_config(self, model_name: str = None) -> Dict[str, Any]:
        """
        解析API配置(统一方法)

        Returns:
            dict with keys: api_key, base_url, is_anthropic, model_name
        """
        if model_name is None:
            model_name = self.model

        api_key = self._get_api_key()
        base_url = self._get_model_base_url()

        # 检测是否为Anthropic模型
        is_anthropic = any(x in model_name.lower() for x in ["anthropic", "claude"])

        return {
            "api_key": api_key,
            "base_url": base_url,
            "is_anthropic": is_anthropic,
            "model_name": model_name
        }

    def _build_system_prompt(self) -> str:
        """使用prompt_builder构建完整的系统提示"""
        try:
            # 获取可用工具列表
            available_tools = set(self.tool_registry.list_tools())

            # MimirAether的skills目录
            mimir_root = Path(__file__).parent.parent
            skills_dir = str(mimir_root / "skills")

            # 使用prompt_builder构建系统提示
            system_prompt = prompt_builder.build_system_prompt(
                model=self.model,
                cwd=os.getcwd(),
                available_tools=available_tools,
                platform=self.platform,
                include_skills=True,
                include_context=True,
                skills_dirs=[skills_dir],
            )

            return system_prompt if system_prompt else self._default_system_prompt()
        except Exception as e:
            logger.warning(f"Failed to build system prompt with prompt_builder: {e}")
            return self._default_system_prompt()

    def _register_builtin_tools(self):
        """注册内置工具（Hermes 模式：工具通过模块导入自注册）

        工具现在通过 tools/ 目录下各模块的 registry.register() 调用自动注册。
        只需导入模块即可触发注册。Skill 工具仍需手动注册。
        """
        import sys
        from pathlib import Path

        # 将MimirAether根目录添加到path
        mimir_root = Path(__file__).parent.parent
        if str(mimir_root) not in sys.path:
            sys.path.insert(0, str(mimir_root))

        # ── 导入工具模块（自注册到 tools.registry.registry） ──
        builtin_count = 0
        mimircore_count = 0
        try:
            import tools.builtin  # noqa: F401 - 导入即触发 registry.register()
            builtin_count = len([e for e in _tool_registry_module.registry._tools.values()
                                if e.toolset in ("file", "code_execution", "web")])
        except ImportError as e:
            logger.warning(f"Failed to import builtin tools: {e}")

        try:
            import tools.mimircore_tool  # noqa: F401 - 导入即触发 registry.register()
            mimircore_count = len([e for e in _tool_registry_module.registry._tools.values()
                                  if e.toolset == "mimircore"])
        except ImportError as e:
            logger.warning(f"Failed to import mimircore tools: {e}")

        logger.info(f"Self-registered {builtin_count} builtin + {mimircore_count} mimircore tools")

        # ── 注册Skill工具（skill_view, skills_list, skill_manage） ──
        try:
            from skills.skills_loader import skill_view as _skill_view_func, skills_list as _skills_list_func
            from skills.skills_loader import skill_manage as _skill_manage_func

            self.tool_registry.register("skill_view", _skill_view_func, SKILL_TOOL_SCHEMAS.get("skill_view", {}))
            self.tool_registry.register("skills_list", _skills_list_func, SKILL_TOOL_SCHEMAS.get("skills_list", {}))
            self.tool_registry.register("skill_manage", _skill_manage_func, SKILL_MANAGE_SCHEMA)

            logger.info("Registered skill tools: skill_view, skills_list, skill_manage")
        except ImportError as e:
            logger.warning(f"Failed to import skill tools: {e}")

    def _fire_stream_delta(self, text: str) -> None:
        """
        触发流式输出回调

        学习自Hermes _fire_stream_delta:
        - 处理段落分隔
        - 调用所有注册的流式回调
        - 记录流式输出的累积文本
        """
        # 如果需要段落分隔,在文本前添加
        if self._stream_needs_break and text and text.strip():
            self._stream_needs_break = False
            text = "\n\n" + text

        # 调用流式回调
        if self.stream_callback:
            try:
                self.stream_callback(text)
            except Exception as e:
                logger.debug(f"Stream callback error: {e}")

        # 累积文本
        self._current_streamed_text += text

    def interrupt(self, message: str = None) -> None:
        """
        请求中断当前工具调用循环

        学习自Hermes interrupt方法:
        - 设置中断标志
        - 信号所有工具中止操作
        """
        self._interrupt_requested = True
        self._interrupt_message = message
        print(f"\n⚡ Interrupt requested: '{message[:40]}...'" if message and len(message) > 40 else f"\n⚡ Interrupt requested: '{message}'" if message else "\n⚡ Interrupt requested")

    def clear_interrupt(self) -> None:
        """清除中断请求"""
        self._interrupt_requested = False
        self._interrupt_message = None

    def is_interrupted(self) -> bool:
        """检查是否被中断"""
        return self._interrupt_requested

    def _has_stream_consumers(self) -> bool:
        """检查是否有流式输出的消费者"""
        return self.stream_callback is not None

    def _strip_think_blocks(self, content: str) -> str:
        """
        去除Think/Reasoning Block

        学习自Hermes _strip_think_blocks:
        - 去除<think>...</think>格式
        - 去除<thinking>...</thinking>格式
        - 去除<reasoning>...</reasoning>格式
        - 去除其他变体
        """
        import re
        # 去除<think>...</think>格式
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        # 去除<thinking>...</thinking>格式
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # 去除<reasoning>...</reasoning>格式
        content = re.sub(r'<reasoning>.*?</reasoning>', '', content, flags=re.DOTALL)
        # 去除<REASONING_SCRATCHPAD>...</REASONING_SCRATCHPAD>格式
        content = re.sub(r'<REASONING_SCRATCHPAD>.*?</REASONING_SCRATCHPAD>', '', content, flags=re.DOTALL)
        # 去除<thought>...</thought>格式
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # 去除所有Think/Reasoning标签
        content = re.sub(r'</?(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)>', '', content, flags=re.IGNORECASE)
        return content

    def _extract_reasoning_from_response(self, response: Dict) -> Optional[str]:
        """
        从模型响应中提取reasoning内容
        
        学习自Hermes _extract_reasoning_from_message：
        支持多种provider格式，统一提取reasoning字段。
        
        Args:
            response: 模型响应字典，包含content和可选的reasoning字段
            
        Returns:
            提取的reasoning文本，或None
        """
        # 优先从response的顶层字段提取（部分provider直接返回）
        if response.get('reasoning'):
            return response['reasoning']
        
        # 有些provider返回reasoning_content
        if response.get('reasoning_content'):
            return response['reasoning_content']
        
        # 从content中提取<reasoning>...</reasoning>块
        content = response.get('content', '')
        if content:
            import re
            # 提取<think>...</think>格式
            match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
            if match:
                return match.group(1).strip()
            # 提取<reasoning>...</reasoning>格式
            match = re.search(r'<reasoning>(.*?)</reasoning>', content, re.DOTALL)
            if match:
                return match.group(1).strip()
            # 提取<thinking>...</thinking>格式
            match = re.search(r'<thinking>(.*?)</thinking>', content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def _deduplicate_tool_calls(self, tool_calls: list) -> list:
        """
        去除重复的工具调用

        学习自Hermes _deduplicate_tool_calls:
        - 基于(tool_name, arguments)唯一性去重
        - 只保留第一个出现的重复调用
        """
        seen = set()
        unique = []
        for tc in tool_calls:
            # 使用统一工具函数提取名称和参数，兼容OpenAI嵌套格式和旧格式
            name = _get_tool_name(tc)
            arguments = _get_tool_arguments(tc)
            key = (name, arguments if isinstance(arguments, str) else json.dumps(arguments, sort_keys=True))
            if key not in seen:
                seen.add(key)
                unique.append(tc)
            else:
                logger.warning(f"Removed duplicate tool call: {name}")
        return unique if len(unique) < len(tool_calls) else tool_calls

    def _repair_tool_call(self, tool_name: str) -> str | None:
        """
        修复错误的工具名称

        学习自Hermes _repair_tool_call:
        1. 尝试小写
        2. 尝试标准化(下划线替代连字符/空格)
        3. 尝试模糊匹配
        """
        if not hasattr(self, 'tool_registry'):
            return None

        valid_names = set(self.tool_registry.list_tools())
        if not valid_names:
            return None

        # 1. 小写匹配
        lowered = tool_name.lower()
        if lowered in valid_names:
            return lowered

        # 2. 标准化匹配
        normalized = lowered.replace('-', '_').replace(' ', '_')
        if normalized in valid_names:
            return normalized

        # 3. 模糊匹配
        import difflib
        matches = difflib.get_close_matches(lowered, valid_names, n=1, cutoff=0.7)
        if matches:
            return matches[0]

        return None

    async def _cleanup_aiohttp_connections(self, session) -> int:
        """
        清理aiohttp死连接

        学习自Hermes _cleanup_dead_connections:
        - 关闭死TCP连接,防止CLOSE-WAIT累积
        - 对于aiohttp,简化处理:关闭并重建session
        """
        closed = 0
        try:
            # aiohttp的connector持有连接池
            connector = getattr(session, '_connector', None)
            if connector is None:
                return 0

            # 获取连接池中的连接
            connections = getattr(connector, '_conns', [])
            if connections:
                # 标记为需要清理
                connector._conns = []
                closed = len(connections)
                logger.debug(f"Cleaned up {closed} aiohttp connections")
        except Exception as e:
            logger.warning(f"Failed to cleanup connections: {e}")

        return closed

    async def _stream_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict],
        tool_schemas: List[Dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[Dict, float]:
        """
        流式调用OpenAI兼容API

        学习自Hermes _interruptible_streaming_api_call:
        - 使用stream=True参数
        - 迭代chunk并调用_fire_stream_delta
        - 返回累积的完整响应

        Returns:
            (response_dict, latency_ms)
        """
        import aiohttp
        import time

        start = time.monotonic()

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # 启用流式
        }

        if tool_schemas:
            payload["tools"] = tool_schemas
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        content_parts = []
        tool_calls_acc = {}
        finish_reason = None
        stream_usage: Optional[Dict[str, Any]] = None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=3600)
                ) as response:
                    latency_ms = (time.monotonic() - start) * 1000

                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Stream API error {response.status}: {error_text[:200]}")

                    # 迭代流式响应
                    async for line in response.content:
                        # 检查是否被中断
                        if self._interrupt_requested:
                            logger.info("Stream interrupted by user")
                            break

                        line = line.decode('utf-8').strip()

                        if not line or not line.startswith('data: '):
                            continue

                        data = line[6:]  # 去掉 'data: '

                        if data == '[DONE]':
                            break

                        try:
                            import json
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        _chunk_usage = chunk.get("usage")
                        if isinstance(_chunk_usage, dict) and _chunk_usage:
                            stream_usage = _chunk_usage

                        # 解析delta
                        choices = chunk.get('choices', [])
                        if not choices:
                            continue

                        delta = choices[0].get('delta', {})

                        # 处理内容
                        if delta.get('content'):
                            text = delta['content']
                            content_parts.append(text)
                            # 如果没有累积的工具调用,流式输出
                            if not tool_calls_acc:
                                self._fire_stream_delta(text)

                        # 处理工具调用
                        if 'tool_calls' in delta:
                            for tc in delta['tool_calls']:
                                index = tc.get('index', 0)
                                if index not in tool_calls_acc:
                                    tool_calls_acc[index] = {
                                        'id': '',
                                        'type': 'function',
                                        'function': {'name': '', 'arguments': ''}
                                    }
                                if tc.get('id'):
                                    tool_calls_acc[index]['id'] = tc['id']
                                if tc.get('function', {}).get('name'):
                                    tool_calls_acc[index]['function']['name'] = tc['function']['name']
                                if tc.get('function', {}).get('arguments'):
                                    tool_calls_acc[index]['function']['arguments'] += tc['function']['arguments']

                        # 处理finish_reason
                        if choices[0].get('finish_reason'):
                            finish_reason = choices[0]['finish_reason']

                    # 构建响应
                    content = ''.join(content_parts)
                    tool_calls = list(tool_calls_acc.values()) if tool_calls_acc else None

                    return {
                        'content': content,
                        'tool_calls': tool_calls,
                        'finish_reason': finish_reason,
                        'usage': stream_usage if isinstance(stream_usage, dict) else {},
                    }, latency_ms

        except Exception as e:
            logger.error(f"Stream API call failed: {e}")
            raise

    def _default_system_prompt(self) -> str:
        """默认系统提示"""
        return """You are MimirAether, an AI assistant powered by advanced reasoning and tool execution capabilities.

Core capabilities:
- Natural language understanding and generation
- Tool execution for various tasks
- Code writing, debugging, and execution
- File operations and system tasks
- Web search and information retrieval
- Memory management across sessions

## Tool Calling Rules (CRITICAL)

When calling tools, you MUST use the exact parameter names defined in the tool schema:

- execute_code: parameter is `code` NOT `command`
- write_file: parameters are `path` and `content`
- read_file: parameter is `path`
- get_env: parameter is `key` (optional `default`)
- web_search: parameter is `query`

You must strictly follow the parameter names in the schema. Do not use alternative names or make assumptions about parameter names.

You can call tools to accomplish tasks. Always provide clear, accurate responses.

## Self-Evolution Guide (When asked to evolve/improve)

When given an evolution task, you MUST:
1. Read the relevant code files first
2. Make ONE small, safe change to the code
3. Use write_file to save the change
4. Report what you changed and why

Small progress is good! Even one line changed is real progress.
Do not just report - you must modify files to show progress.

Do not be afraid of mistakes - they can be fixed. Report your changes."""

    def _compressor_sync_usage_from_llm(
        self, response: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> None:
        """Feed API usage (or rough estimate) into ``self.compressor`` for ``needs_compression``."""
        usage = response.get("usage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            usage = {}
        pt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        ct = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        if pt <= 0:
            try:
                pt = int(model_metadata.estimate_messages_tokens_rough(messages))
            except Exception:
                pt = 0
        if pt <= 0 and ct <= 0:
            return
        total = usage.get("total_tokens")
        if total is None:
            total = pt + ct
        try:
            self.compressor.update_from_response(
                {
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": int(total),
                }
            )
        except Exception as _e:
            logger.debug("compressor.update_from_response skipped: %s", _e)

    async def chat(self, message: str) -> str:
        """
        主聊天接口

        处理单条用户消息,返回助手响应
        """
        # 运行对话(消息添加由run_conversation统一管理)
        response = await self.run_conversation(message)

        return response

    async def run_conversation(self, user_message: str) -> str:
        """
        完整对话运行

        学习自Hermes run_conversation:
        - 构建消息列表(每次迭代重建)
        - 调用模型API(带超时控制)
        - 处理工具调用
        - 管理迭代预算
        """
        # 生成会话ID(用于Insights追踪)
        session_id = str(uuid.uuid4())

        # 开始轨迹记录
        if self.save_trajectories:
            self._start_trajectory()

        # 用MemoryFencer隔离用户消息(防止注入)
        fenced_msg = self.fencer.fence(user_message)
        if fenced_msg.was_modified:
            if fenced_msg.warnings:
                logger.warning(f"User message modified by fencer: {fenced_msg.warnings}")
            else:
                logger.debug("User message adjusted by fencer (e.g. tag wrap); no warning list")

        # 学习自Hermes: @引用展开
        # 展开 @file:xxx, @folder:xxx 等引用
        message_text = fenced_msg.content
        if "@" in message_text:
            try:
                from .context_references import preprocess_context_references
                ref_result = preprocess_context_references(
                    message_text,
                    cwd=os.getcwd(),
                    context_length=self._context_length or 128000
                )
                if ref_result.references:
                    logger.info(f"@引用展开: {len(ref_result.references)}个引用, {ref_result.injected_tokens} tokens")
                    if ref_result.expanded:
                        message_text = ref_result.message
            except Exception as e:
                logger.debug(f"@引用展开失败: {e}")

        effective_user_message = message_text

        # 添加用户消息到历史(使用 @ 展开后的最终文本)
        self.conversation_history.append(Message(
            role=MessageRole.USER,
            content=effective_user_message
        ))

        # ============================================================
        # ============================================================
        # Hermes风格执行元数据初始化(学习自Hermes)
        # ============================================================
        self._tool_errors = []
        self._reasoning_per_turn = []
        self._current_turn = 0
        
        # 断点续传:检查是否存在未完成的检查点
        # ============================================================
        task_id = hashlib.sha256(effective_user_message.encode('utf-8')).hexdigest()[:16]
        checkpoint_mgr = self._checkpoint_backend
        recovered_from_checkpoint = False

        checkpoint = checkpoint_mgr.load_checkpoint(task_id)
        if checkpoint:
            logger.info(f"[Checkpoint] Found checkpoint for task {task_id}, recovering from step {checkpoint.current_step}")
            # 从检查点恢复对话历史
            try:
                recovered_messages = []
                for msg_data in checkpoint.conversation_history:
                    role = MessageRole(msg_data.get('role', 'user'))
                    recovered_messages.append(Message(
                        role=role,
                        content=msg_data.get('content', ''),
                        name=msg_data.get('name'),
                        tool_calls=msg_data.get('tool_calls'),
                        tool_call_id=msg_data.get('tool_call_id'),
                    ))
                # 恢复对话历史(保留用户消息,加上恢复的历史)
                self.conversation_history = [self.conversation_history[0]] + recovered_messages
                # 恢复budget已使用次数
                for _ in range(checkpoint.iteration_used):
                    await self.budget.consume()
                recovered_from_checkpoint = True
                logger.info(f"[Checkpoint] Recovered {len(recovered_messages)} messages, {checkpoint.iteration_used} iterations")
            except Exception as e:
                logger.warning(f"[Checkpoint] Recovery failed: {e}, starting fresh")

        # Plugin hook: on_session_start
        # 会话开始时执行
        try:
            self._invoke_hook(
                "on_session_start",
                session_id=session_id,
                model=self.model,
                platform=self.platform,
            )
        except Exception as e:
            logger.warning(f"on_session_start hook failed: {e}")

        # 限制历史长度,防止内存耗尽
        if len(self.conversation_history) > self.max_history_length:
            # 保留系统消息和最新的对话
            system_msgs = [m for m in self.conversation_history if m.role == MessageRole.SYSTEM]
            other_msgs = [m for m in self.conversation_history if m.role != MessageRole.SYSTEM]
            self.conversation_history = system_msgs + other_msgs[-self.max_history_length:]

        # 断点续传:用于跟踪当前步骤
        _current_step = checkpoint.current_step if checkpoint else 0

        try:
            # 恢复主运行时(Fallback后)
            self._restore_primary_runtime()

            # 主循环
            while True:
                # 检查是否被中断
                if self._interrupt_requested:
                    logger.info("Conversation interrupted by user")
                    # 保存断点(中断时保留进度)
                    checkpoint_mgr.save_checkpoint(
                        task_id=task_id,
                        state={
                            "conversation_history": [{"role": m.role.value, "content": m.content, "name": m.name, "tool_calls": m.tool_calls, "tool_call_id": m.tool_call_id} for m in self.conversation_history[1:]],
                            "iteration_used": self.budget._used,
                            "session_id": session_id,
                            "user_message": effective_user_message,
                        },
                        current_step=_current_step,
                        next_action="等待用户继续或重新开始",
                    )
                    return f"对话已被中断。" + (f" 您的输入: {self._interrupt_message}" if self._interrupt_message else "")

                # 检查预算
                if not await self.budget.consume():
                    logger.warning("Iteration budget exhausted")
                    return "抱歉,任务迭代次数已达上限。"
                
                # Hermes风格:每轮递增(学习自Hermes)
                self._current_turn += 1

                # 触发step_callback(每步执行后)
                if self.step_callback:
                    try:
                        self.step_callback()
                    except Exception as e:
                        logger.warning(f"step_callback error: {e}")

                # ============================================================
                # 断点续传:每个迭代开始时保存检查点
                # ============================================================
                _current_step += 1
                checkpoint_mgr.save_checkpoint(
                    task_id=task_id,
                    state={
                        "conversation_history": [{"role": m.role.value, "content": m.content, "name": m.name, "tool_calls": m.tool_calls, "tool_call_id": m.tool_call_id} for m in self.conversation_history[1:]],
                        "iteration_used": self.budget._used,
                        "session_id": session_id,
                        "user_message": effective_user_message,
                    },
                    current_step=_current_step,
                    next_action="执行下一步迭代",
                )

                # 每次迭代都重建消息列表(使用当前全部历史)
                messages = self._build_full_messages()

                # 用ContextCompressor压缩长对话
                if self.compressor.needs_compression(messages):
                    compressed_messages, comp_result = self.compressor.compress(messages)
                    logger.info(
                        f"Compressed {comp_result.original_count} -> "
                        f"{comp_result.compressed_count} messages "
                        f"(ratio: {comp_result.compressed_tokens/comp_result.original_tokens:.2f})" if comp_result.original_tokens > 0 else "(no ratio)"
                    )
                    messages = compressed_messages

                # Plugin hook: pre_llm_call
                # 在LLM调用前执行,允许插件注入上下文
                try:
                    pre_results = self._invoke_hook(
                        "pre_llm_call",
                        user_message=effective_user_message,
                        conversation_history=list(messages),
                        model=self.model,
                    )
                    # 如果有hook返回结果,注入到用户消息
                    for result in pre_results:
                        if isinstance(result, dict) and result.get("context"):
                            context_text = str(result["context"])
                            if messages and messages[0].get("role") == "system":
                                messages[0] = {"role": "system", "content": messages[0].get("content", "") + "\n\n" + context_text}
                except Exception as e:
                    logger.warning(f"pre_llm_call hook failed: {e}")

                # 调用模型(带超时控制)
                try:
                    response, latency_ms = await asyncio.wait_for(
                        self._call_model_with_tokens(messages, session_id),
                        timeout=3600.0  # 1小时超时
                    )
                except asyncio.TimeoutError:
                    logger.error("Model call timed out")
                    return "抱歉,模型响应超时,请重试。"
                except Exception as e:
                    err_str = str(e)
                    logger.error(f"Model call failed: {e}")
                    
                    # 自动恢复：检测 conversation_history 污染
                    # 症状：DeepSeek 400 "tool must be a response to preceding tool_calls"
                    # 原因：中断/错误导致 tool_calls 写了但是 tool result 没写
                    is_orphan_tool = (
                        "tool' must be a response" in err_str
                        or "tool_calls" in err_str.lower() and "tool" in err_str.lower()
                    )
                    if is_orphan_tool and self.conversation_history:
                        logger.warning(
                            "Detected orphan tool messages in conversation_history — "
                            "cleaning up last corrupted turn to recover"
                        )
                        # 删除最后一个 assistant(tool_calls) 及其后所有孤立的 tool 消息
                        cut = len(self.conversation_history)
                        while cut > 0:
                            msg = self.conversation_history[cut - 1]
                            if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
                                # 找到最近一个有 tool_calls 的 assistant 消息
                                # 把它改成纯文本（去掉 tool_calls），然后删除后面所有消息
                                self.conversation_history = self.conversation_history[:cut - 1]
                                logger.info(
                                    "Conversation history cleaned: removed %d corrupted message(s) "
                                    "after last tool_calls at position %d",
                                    len(self.conversation_history) - (cut - 1),
                                    cut - 1,
                                )
                                break
                            cut -= 1
                        # 重试
                        continue
                    
                    # 尝试激活Fallback模型
                    if self._try_activate_fallback():
                        # Fallback激活成功,重试当前迭代
                        continue
                    # 通用错误,不泄露内部细节
                    return "抱歉,模型调用失败,请稍后重试。"

                self._compressor_sync_usage_from_llm(response, messages)

                # 添加助手响应到历史(仅当有内容或tool_calls时)
                response_content = response.get("content") or ""
                response_tool_calls = response.get("tool_calls")
                response_reasoning = response.get("reasoning_content")  # DeepSeek V4 Pro
                if response_content or response_tool_calls:
                    self.conversation_history.append(Message(
                        role=MessageRole.ASSISTANT,
                        content=response_content,
                        tool_calls=response_tool_calls,
                        reasoning_content=response_reasoning
                    ))
                
                # Hermes风格:提取reasoning内容(学习自Hermes)
                reasoning = self._extract_reasoning_from_response(response)
                self._reasoning_per_turn.append(reasoning)
                if reasoning:
                    logger.debug(f"Turn {self._current_turn}: extracted reasoning ({len(reasoning)} chars)")

                # Plugin hook: post_llm_call
                # 在LLM调用后执行,允许插件处理响应
                try:
                    self._invoke_hook(
                        "post_llm_call",
                        response=response,
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"post_llm_call hook failed: {e}")

                # Fallback tool call parser: if the API didn't return
                # structured tool_calls but content contains <tool_call>
                # tags, parse them client-side. This handles edge cases
                # where servers cannot parse tool calls natively.
                _raw_tool_calls = response.get("tool_calls")
                if not _raw_tool_calls and response_content and "<tool_call>" in response_content:
                    import re as _re
                    import uuid as _uuid
                    _pattern = _re.compile(
                        r"<tool_call>\s*(.*?)\s*</tool_call>|<tool_call>\s*(.*)",
                        _re.DOTALL,
                    )
                    _matches = _pattern.findall(response_content)
                    if _matches:
                        _parsed_calls = []
                        for _m in _matches:
                            _raw = _m[0] or _m[1]
                            if not _raw.strip():
                                continue
                            try:
                                import json as _json
                                _data = _json.loads(_raw)
                                if "name" in _data:
                                    _parsed_calls.append({
                                        "id": f"call_{_uuid.uuid4().hex[:8]}",
                                        "type": "function",
                                        "function": {
                                            "name": _data["name"],
                                            "arguments": _json.dumps(
                                                _data.get("arguments", {}),
                                                ensure_ascii=False,
                                            ),
                                        },
                                    })
                            except Exception:
                                pass
                        if _parsed_calls:
                            _tag_idx = response_content.find("<tool_call>")
                            _clean_content = response_content[:_tag_idx].strip()
                            response["tool_calls"] = _parsed_calls
                            response["content"] = _clean_content or ""
                            logger.debug(
                                "Fallback parser extracted %d tool calls from raw content",
                                len(_parsed_calls),
                            )

                # 检查是否有工具调用
                if response.get("tool_calls") and response_content:
                    # 同时有文本和工具调用:先执行工具,再继续生成响应
                    # 去重工具调用
                    unique_tool_calls = self._deduplicate_tool_calls(response["tool_calls"])
                    tool_results = await self._execute_tools(unique_tool_calls, turn=self._current_turn)

                    # Budget control: persist large tool results
                    # to prevent context window overflow (3-layer defense).
                    try:
                        from tools.tool_result_storage import (
                            maybe_persist_tool_result,
                            enforce_turn_budget,
                        )
                        from tools.budget_config import DEFAULT_BUDGET
                        from tools.terminal_tool import get_active_env

                        _env = get_active_env(None)
                        for _tr in tool_results:
                            _tr.content = maybe_persist_tool_result(
                                content=_tr.content,
                                tool_name="unknown",
                                tool_use_id=_tr.tool_call_id,
                                env=_env,
                                config=DEFAULT_BUDGET,
                            )
                        _tool_msgs = [
                            {"role": "tool", "tool_call_id": r.tool_call_id, "content": r.content}
                            for r in tool_results
                        ]
                        enforce_turn_budget(_tool_msgs, env=_env, config=DEFAULT_BUDGET)
                        for i, r in enumerate(tool_results):
                            r.content = _tool_msgs[i]["content"]
                    except Exception as _e:
                        logger.debug("Budget control skipped: %s", _e)

                    # 添加工具结果到历史
                    for result in tool_results:
                        self.conversation_history.append(Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=result.tool_call_id
                        ))

                    # 工具调用后 refund(只refund一次,无论多少工具)
                    await self.budget.refund()

                    # 继续循环,让模型基于工具结果生成最终响应
                    continue

                if response.get("tool_calls"):
                    # 只有工具调用,没有文本:执行工具
                    # 去重工具调用
                    unique_tool_calls = self._deduplicate_tool_calls(response["tool_calls"])
                    tool_results = await self._execute_tools(unique_tool_calls, turn=self._current_turn)

                    # Budget control: persist large tool results
                    # to prevent context window overflow (3-layer defense).
                    try:
                        from tools.tool_result_storage import (
                            maybe_persist_tool_result,
                            enforce_turn_budget,
                        )
                        from tools.budget_config import DEFAULT_BUDGET
                        from tools.terminal_tool import get_active_env

                        _env = get_active_env(None)
                        for _tr in tool_results:
                            _tr.content = maybe_persist_tool_result(
                                content=_tr.content,
                                tool_name="unknown",
                                tool_use_id=_tr.tool_call_id,
                                env=_env,
                                config=DEFAULT_BUDGET,
                            )
                        _tool_msgs = [
                            {"role": "tool", "tool_call_id": r.tool_call_id, "content": r.content}
                            for r in tool_results
                        ]
                        enforce_turn_budget(_tool_msgs, env=_env, config=DEFAULT_BUDGET)
                        for i, r in enumerate(tool_results):
                            r.content = _tool_msgs[i]["content"]
                    except Exception as _e:
                        logger.debug("Budget control skipped: %s", _e)

                    # 添加工具结果到历史
                    for result in tool_results:
                        self.conversation_history.append(Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=result.tool_call_id
                        ))

                    # 工具调用后 refund(只refund一次,无论多少工具)
                    await self.budget.refund()

                    # 继续循环(下次迭代会重建messages)
                    continue

                # 文本响应,结束
                # 去除Think Block
                response_content = self._strip_think_blocks(response_content)

                # ============================================================
                # 断点续传:任务成功完成,清除检查点
                # ============================================================
                checkpoint_mgr.clear_checkpoint(task_id)

                # Plugin hook: on_session_end
                # 会话结束时执行
                try:
                    self._invoke_hook(
                        "on_session_end",
                        session_id=session_id,
                        response=response_content,
                    )
                except Exception as e:
                    logger.warning(f"on_session_end hook failed: {e}")

                return response_content
        finally:
            # ============================================================
            # 断点续传:finally中确保检查点被清除
            # ============================================================
            checkpoint_mgr.clear_checkpoint(task_id)

            # 保存轨迹
            if self.save_trajectories:
                self._save_trajectory(completed=True)

    def _build_full_messages(self) -> List[Dict]:
        """构建完整消息列表(用于API调用)"""
        messages = []

        # 系统提示
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })

        # 检测是否需要reasoning_content传播(DeepSeek V4 Pro等模型需要)
        needs_propagation = self._needs_reasoning_propagation()
        has_seen_reasoning = False  # 标记是否已见过带reasoning的assistant消息

        # 对话历史(从开始到最新,全部包含)
        for msg in self.conversation_history:
            msg_dict = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls

            # reasoning_content传播: DeepSeek V4 Pro要求所有assistant消息必须包含该字段
            if msg.role == MessageRole.ASSISTANT:
                if needs_propagation:
                    # 如果之前已见过带reasoning的assistant，当前必须也有
                    if has_seen_reasoning:
                        msg_dict["reasoning_content"] = msg.reasoning_content or ""
                    else:
                        # 第一个assistant消息，有就传，没有就不传
                        msg_dict["reasoning_content"] = msg.reasoning_content
                    if msg.reasoning_content:
                        has_seen_reasoning = True
                elif msg.reasoning_content:
                    msg_dict["reasoning_content"] = msg.reasoning_content
            elif msg.reasoning_content:
                # tool消息的reasoning_content也传递
                msg_dict["reasoning_content"] = msg.reasoning_content

            messages.append(msg_dict)

        return messages

    def _needs_reasoning_propagation(self) -> bool:
        """检测当前模型是否需要reasoning_content传播。

        DeepSeek V4 Pro等模型在thinking模式下，
        如果对话历史中有assistant消息携带了reasoning_content，
        则后续所有assistant消息也必须包含该字段。
        """
        model_lower = self.model.lower() if self.model else ""

        # 仅对支持thinking模式的模型进行检查
        thinking_models = ("deepseek", "kimi", "moonshot")
        if not any(tm in model_lower for tm in thinking_models):
            return False

        # 检查对话历史中是否有assistant消息携带了reasoning_content
        for msg in self.conversation_history:
            if msg.role == MessageRole.ASSISTANT and msg.reasoning_content:
                return True

        return False
    async def _builtin_call_model_with_tokens(
        self, messages: List[Dict], session_id: str
    ) -> tuple[Dict, float]:
        """
        内置模型调用实现（HTTP/Anthropic/OpenAI 兼容路径）。

        统一入口:先解析API配置和工具schemas(只做一次),
        然后根据模型类型和流式需求分发到不同路径。
        对外请通过 ``_call_model_with_tokens`` → ``LlmInvocationPort``。

        Returns:
            (response_dict, latency_ms)
        """
        import time
        start = time.monotonic()

        import os
        import aiohttp

        # 1. 解析API配置(只做一次)
        model_name = self.model if hasattr(self, 'model') and self.model else os.environ.get("LLM_MODEL", "deepseek-chat")
        api_config = self._resolve_api_config(model_name)
        api_key = api_config["api_key"]
        base_url = api_config["base_url"]
        is_anthropic = api_config["is_anthropic"]
        model_name = api_config["model_name"]

        if not api_key:
            raise ValueError(f"API key not set for model {model_name}")

        # 2. 获取context_length和max_tokens(只做一次)
        context_length = model_metadata.get_model_context_length(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
        )
        max_output_tokens = model_metadata.get_anthropic_max_output(model_name) if "claude" in model_name.lower() else 4096
        max_tokens = min(max_output_tokens, context_length // 4) if context_length else 4096

        # 3. 构建工具schemas（使用统一 registry，Hermes 模式）
        tool_schemas = _tool_registry_module.registry.get_definitions(
            set(_tool_registry_module.registry.get_all_tool_names())
        )

        # 4. 分发到具体调用路径
        # 路径A: Anthropic API
        if is_anthropic:
            return await self._call_anthropic_api(
                model_name=model_name,
                messages=messages,
                api_key=api_key,
                base_url=base_url,
                context_length=context_length,
                session_id=session_id,
                start=start,
            )

        # 路径B: 流式调用(OpenAI兼容)
        if self._has_stream_consumers():
            return await self._stream_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model_name,
                messages=messages,
                tool_schemas=tool_schemas,
                max_tokens=max_tokens,
                temperature=0.7,
            )

        # 路径C: 标准非流式调用(OpenAI兼容)
        # 转换model名为API接受的格式
        # 注意: OpenRouter的model格式是"provider/model-name"，而官方API通常只需要"model-name"
        # 根据base_url判断: openrouter保持原名，官方API需要转换
        api_model_name = model_name
        base_url_lower = base_url.lower()
        is_openrouter = "openrouter" in base_url_lower
        
        # 只有在官方API(非openrouter)且model包含/时才转换
        if ("deepseek" in model_name.lower() or "minimax" in model_name.lower()) and not is_openrouter:
            if "/" in model_name:
                api_model_name = model_name.split("/")[-1]

        payload = {
            "model": api_model_name,
            "messages": messages,
            "temperature": 1.0 if "kimi-k2" in model_name else 0.7,
            "max_tokens": max_tokens,
            "tools": tool_schemas,
            "tool_choice": "auto"
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=3600)
                ) as response:
                    latency_ms = (time.monotonic() - start) * 1000

                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning(f"API call failed: {response.status}, response: {error_text[:500]}")
                        raise RuntimeError(f"Model API request failed: {response.status}")

                    result = await response.json()

                    # 安全提取助手响应(边界检查)
                    choices = result.get("choices")
                    if not choices or len(choices) == 0:
                        raise RuntimeError("Invalid API response: no choices")

                    assistant_message = choices[0].get("message")
                    if not assistant_message:
                        raise RuntimeError("Invalid API response: no message in choice")

                    content = assistant_message.get("content") or ""
                    tool_calls = assistant_message.get("tool_calls")

                    # 记录token使用
                    usage = result.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    if prompt_tokens > 0:
                        self.insights.record(
                            MetricType.TOKEN_INPUT,
                            float(prompt_tokens),
                            metadata={"session_id": session_id, "platform": self.platform, "model": self.model}
                        )
                    if completion_tokens > 0:
                        self.insights.record(
                            MetricType.TOKEN_OUTPUT,
                            float(completion_tokens),
                            metadata={"session_id": session_id, "platform": self.platform, "model": self.model}
                        )

                    self.insights.record(
                        MetricType.LATENCY,
                        latency_ms,
                        metadata={"session_id": session_id, "platform": self.platform}
                    )

                    return {
                        "content": content,
                        "tool_calls": tool_calls,
                        "reasoning_content": assistant_message.get("reasoning_content"),
                        "usage": usage,
                    }, latency_ms

        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                if self._credential_pool:
                    current = self._credential_pool.current()
                    if current:
                        self._credential_pool.mark_exhausted(current, status_code=429, error_message=str(e))
                    next_cred = self._credential_pool.select()
                    if next_cred:
                        logger.info(f"Credential exhausted, rotated to: {next_cred.label}")
                raise RuntimeError(f"Rate limited (429): {e}")
            raise RuntimeError(f"API error ({e.status}): {e}")
        except aiohttp.ClientError:
            raise RuntimeError("Network error during model call")

    async def _call_model_with_tokens(
        self, messages: List[Dict], session_id: str
    ) -> tuple[Dict, float]:
        """委托给当前 ``llm_backend``（默认 :class:`_BuiltinLlmBackend`）。"""
        return await self._llm_backend.call_model_with_tokens(messages, session_id)

    def set_llm_backend(self, backend: LlmInvocationPort) -> None:
        """运行时切换 LLM 后端（须实现 :class:`~agent.llm_port.LlmInvocationPort`）。"""
        self._llm_backend = backend

    def set_tool_backend(self, backend: ToolInvocationPort) -> None:
        """运行时切换工具批处理后端（须实现 :class:`~agent.tool_port.ToolInvocationPort`）。"""
        self._tool_backend = backend

    def set_session_backend(self, backend: SessionRestorePort) -> None:
        """运行时切换会话恢复后端（须实现 :class:`~agent.session_port.SessionRestorePort`）。"""
        self._session_backend = backend

    def set_session_db_factory(self, factory: SessionDbClientFactory) -> None:
        """运行时切换 SessionDB 工厂（影响后续 ``create_session_db``；已构造的 ``insights`` 不变）。"""
        self._session_db_factory = factory

    def set_checkpoint_backend(self, backend: CheckpointPersistencePort) -> None:
        """运行时切换检查点后端（须实现 :class:`~agent.checkpoint_port.CheckpointPersistencePort`）。"""
        self._checkpoint_backend = backend

    async def _call_anthropic_api(
        self,
        model_name: str,
        messages: List[Dict],
        api_key: str,
        base_url: str,
        context_length: int,
        session_id: str,
        start: float,
    ) -> tuple[Dict, float]:
        """使用Anthropic API调用模型"""
        import aiohttp

        # 使用anthropic_adapter转换消息格式
        system, anthropic_messages = anthropic_adapter.convert_messages_to_anthropic(
            messages,
            base_url=base_url
        )

        # 构建Anthropic请求参数
        max_output = anthropic_adapter.get_anthropic_max_output(model_name)
        max_tokens = min(max_output, context_length // 4) if context_length else max_output

        kwargs = anthropic_adapter.build_anthropic_kwargs(
            model=model_name,
            messages=messages,  # 传入原始消息,adapter会转换
            tools=None,  # 暂时不传tools
            max_tokens=max_tokens,
            context_length=context_length,
            base_url=base_url,
        )

        # 构建请求头
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        # 发送请求
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/v1/messages",
                    headers=headers,
                    json=kwargs,
                    timeout=aiohttp.ClientTimeout(total=3600)
                ) as response:
                    latency_ms = (time.monotonic() - start) * 1000

                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning(f"Anthropic API call failed: {response.status}")
                        raise RuntimeError(f"Anthropic API request failed: {response.status}")

                    result = await response.json()

                    # 使用anthropic_adapter标准化响应
                    normalized_response, finish_reason = anthropic_adapter.normalize_anthropic_response(
                        result,
                        strip_tool_prefix=True,
                    )

                    content = normalized_response.content or ""
                    tool_calls = None
                    if normalized_response.tool_calls:
                        tool_calls = []
                        for tc in normalized_response.tool_calls:
                            tool_calls.append({
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                            })

                    # 提取usage信息
                    usage = result.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)

                    if input_tokens > 0:
                        self.insights.record(
                            MetricType.TOKEN_INPUT,
                            float(input_tokens),
                            metadata={
                                "session_id": session_id,
                                "platform": self.platform,
                                "model": self.model,
                            }
                        )
                    if output_tokens > 0:
                        self.insights.record(
                            MetricType.TOKEN_OUTPUT,
                            float(output_tokens),
                            metadata={
                                "session_id": session_id,
                                "platform": self.platform,
                                "model": self.model,
                            }
                        )

                    # 记录延迟
                    self.insights.record(
                        MetricType.LATENCY,
                        latency_ms,
                        metadata={
                            "session_id": session_id,
                            "platform": self.platform,
                        }
                    )

                    return {
                        "content": content,
                        "tool_calls": tool_calls,
                        "usage": {
                            "prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens,
                        },
                    }, latency_ms

        except aiohttp.ClientError as e:
            logger.error(f"Anthropic API network error: {e}")
            raise RuntimeError(f"Network error during Anthropic API call: {e}")

    async def _execute_tools(self, tool_calls: List[Dict], turn: int = 0) -> List[ToolResult]:
        """委托给当前 ``tool_backend``（默认 :class:`_BuiltinToolBackend`）。"""
        return await self._tool_backend.execute_tools(tool_calls, turn)

    async def _builtin_execute_tools(self, tool_calls: List[Dict], turn: int = 0) -> List[ToolResult]:
        """
        内置工具批处理：并发限制、单工具超时、registry 分发。

        学习自Hermes _execute_tools：
        - 收集ToolError实例用于元数据
        - 支持turn参数用于错误追踪
        
        Args:
            tool_calls: 工具调用列表
            turn: 当前轮次(用于错误记录)
        """
        # 检查是否被中断
        if self._interrupt_requested:
            logger.info("Tool execution skipped: interrupt requested — returning error placeholders for %d tool(s)", len(tool_calls))
            # 关键修复：中断时不能返回空列表！必须给每个 tool_call 补一个错误结果，
            # 否则 conversation_history 中 assistant(tool_calls) 后面缺 tool result，
            # 导致下次 API 调用时 DeepSeek 400: "tool must be a response to tool_calls"
            return [
                ToolResult(
                    tool_call_id=_get_tool_id(tc) or "unknown",
                    content="Tool execution skipped: agent was interrupted",
                    is_error=True
                )
                for tc in tool_calls
            ]

        results = []

        async def execute_with_semaphore(tool_call: Dict) -> ToolResult:
            async with self._tool_semaphore:
                try:
                    return await asyncio.wait_for(
                        self._execute_single_tool(tool_call, turn),
                        timeout=30.0  # 单工具30秒超时
                    )
                except asyncio.TimeoutError:
                    tool_name = _get_tool_name(tool_call) or 'unknown'
                    logger.warning(f"Tool execution timed out: {tool_name}")
                    # Hermes风格:收集ToolError
                    self._tool_errors.append(ToolError(
                        turn=turn,
                        tool_name=tool_name,
                        arguments=str(_get_tool_arguments(tool_call))[:200],
                        error="TimeoutError",
                        tool_result="Error: tool execution timed out",
                    ))
                    return ToolResult(
                        tool_call_id=_get_tool_id(tool_call) or "unknown",
                        content="Error: tool execution timed out",
                        is_error=True
                    )
                except (ValueError, TypeError, KeyError) as e:
                    tool_name = _get_tool_name(tool_call) or 'unknown'
                    logger.warning(f"Tool execution parameter error: {tool_name}: {e}")
                    # Hermes风格:收集ToolError
                    self._tool_errors.append(ToolError(
                        turn=turn,
                        tool_name=tool_name,
                        arguments=str(_get_tool_arguments(tool_call))[:200],
                        error=f"{type(e).__name__}: {e}",
                        tool_result=f"Error: {type(e).__name__} - {e}",
                    ))
                    return ToolResult(
                        tool_call_id=_get_tool_id(tool_call) or "unknown",
                        content=f"Error: {type(e).__name__} - {e}",
                        is_error=True
                    )
                except Exception as e:
                    tool_name = _get_tool_name(tool_call) or 'unknown'
                    logger.error(f"Tool execution error: {tool_name}: {e}")
                    # Hermes风格:收集ToolError
                    self._tool_errors.append(ToolError(
                        turn=turn,
                        tool_name=tool_name,
                        arguments=str(_get_tool_arguments(tool_call))[:200],
                        error=f"{type(e).__name__}: {e}",
                        tool_result=f"Error: {type(e).__name__} - {e}",
                    ))
                    return ToolResult(
                        tool_call_id=_get_tool_id(tool_call) or "unknown",
                        content=f"Error: {type(e).__name__} - {e}",
                        is_error=True
                    )

        # 并发执行所有工具(受 semaphore 限制)
        tasks = [execute_with_semaphore(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                err_name = type(result).__name__
                err_msg = str(result)
                tool_call = tool_calls[i]
                tool_name = _get_tool_name(tool_call) or 'unknown'
                
                # 记录详细日志但不暴露给LLM
                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(f"Tool execution timed out: {tool_name}")
                    content = "Error: tool execution timed out"
                else:
                    logger.warning(f"Tool execution exception ({err_name}): {tool_name}")
                    content = "Error: tool execution failed"
                
                # Hermes风格:收集ToolError
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=tool_name,
                    arguments=str(_get_tool_arguments(tool_call))[:200],
                    error=f"{err_name}: {err_msg}",
                    tool_result=content,
                ))
                
                processed_results.append(ToolResult(
                    tool_call_id=_get_tool_id(tool_call) or "unknown",
                    content=content,
                    is_error=True
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_single_tool(self, tool_call: Dict, turn: int = 0) -> ToolResult:
        """
        执行单个工具调用
        
        学习自Hermes _execute_single_tool：
        - 收集ToolError实例用于元数据
        - 支持turn参数用于错误追踪
        
        Args:
            tool_call: 工具调用
            turn: 当前轮次(用于错误记录)
        """
        # 获取tool_call的id
        tool_call_id = _get_tool_id(tool_call) or "unknown"

        # 处理OpenAI格式:{type: 'function', function: {name, arguments}}
        if tool_call.get("type") == "function" and "function" in tool_call:
            func_name = tool_call["function"].get("name", "")
            raw_args = tool_call["function"].get("arguments", {})
        else:
            # 兼容旧格式
            func_name = tool_call.get("name", "")
            raw_args = tool_call.get("arguments", {})

        # pre_tool_call hook 已移除(从VALID_HOOKS中删除)- 曾导致无限循环bug

        # 触发tool_start_callback
        if self.tool_start_callback:
            try:
                args_preview = json.dumps(raw_args)[:200] if raw_args else "{}"
                self.tool_start_callback(func_name, args_preview)
            except Exception as e:
                logger.warning(f"tool_start_callback error: {e}")

        # 校验必需字段
        if not tool_call_id or tool_call_id == "unknown":
            logger.warning(f"SKIP tool_call: missing 'id' field: {tool_call}")
            # Hermes风格:收集ToolError
            self._tool_errors.append(ToolError(
                turn=turn,
                tool_name=func_name or "unknown",
                arguments=str(raw_args)[:200],
                error="Missing tool_call id field",
                tool_result="Error: tool_call missing 'id' field",
            ))
            return ToolResult(
                tool_call_id="unknown",
                content="Error: tool_call missing 'id' field",
                is_error=True
            )
        if not func_name:
            logger.warning(f"SKIP tool_call: missing 'name' field: {tool_call}")
            # Hermes风格:收集ToolError
            self._tool_errors.append(ToolError(
                turn=turn,
                tool_name="unknown",
                arguments=str(raw_args)[:200],
                error="Missing tool_call name field",
                tool_result="Error: tool_call missing 'name' field",
            ))
            return ToolResult(
                tool_call_id=tool_call_id,
                content="Error: tool_call missing 'name' field",
                is_error=True
            )

        try:
            # 防御性处理 arguments 类型
            arguments = raw_args if isinstance(raw_args, dict) else {}
            if isinstance(raw_args, str):
                # 如果是字符串,尝试解析为 dict
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError as e:
                    logger.warning(f"SINDRI_DEBUG: JSONDecodeError for {func_name}, raw_args type={type(raw_args)}, len={len(str(raw_args))}, chars={repr(str(raw_args)[:200])}")
                    # sindri: 为 execute_code 工具尝试修复
                    if func_name == "execute_code" and isinstance(raw_args, str):
                        logger.info(f"execute_code: sindri fix - wrapping raw code string as {{code: ...}}")
                        arguments = {"code": raw_args}
                    elif func_name == "write_file" and isinstance(raw_args, str):
                        rep = _parse_write_file_arguments_string(raw_args)
                        if rep is not None:
                            arguments = rep
                            logger.info(
                                "write_file: repaired arguments path_len=%d content_len=%d",
                                len(str(rep.get("path", ""))),
                                len(str(rep.get("content", ""))),
                            )
                        else:
                            self._tool_errors.append(ToolError(
                                turn=turn,
                                tool_name=func_name,
                                arguments=str(raw_args)[:200],
                                error=f"write_file needs path and content",
                                tool_result="Error: write_file requires path and content in JSON format",
                            ))
                            return ToolResult(
                                tool_call_id=tool_call_id,
                                content="Error: write_file requires path and content in JSON format",
                                is_error=True
                            )
                    else:
                        # 其他工具，尝试将raw_args作为纯字符串处理
                        logger.info(f"Unknown tool {func_name}: treating raw_args as string")
                        arguments = {"raw": raw_args}
            # sindri: 深度修复 execute_code 参数
            if func_name == "execute_code" and isinstance(arguments, dict):
                if "code" not in arguments:
                    # arguments可能是 {"type": "function", ...} 格式或缺少code字段
                    if len(arguments) == 1 and "type" in arguments:
                        # OpenAI嵌套格式，跳过
                        pass
                    else:
                        logger.warning(f"execute_code: no 'code' field in arguments, attempting修复")
                        # 尝试从其他字段提取code或使用整个arguments作为code
                        for k, v in arguments.items():
                            if k != "type" and isinstance(v, str):
                                arguments = {"code": v}
                                logger.info(f"execute_code: 使用字段 '{k}' 作为code")
                                break
                        else:
                            # 如果没有找到合适的字符串字段，尝试用str(arguments)
                            arguments = {"code": str(arguments)}
            # sindri: 深度修复 write_file 参数
            if func_name == "write_file" and isinstance(arguments, dict):
                if "content" not in arguments and "path" not in arguments:
                    # 尝试从其他字段提取path和content
                    logger.warning(f"write_file: no 'path' or 'content' field, attempting修复")
                    for k, v in arguments.items():
                        if k == "path" or k == "file_path" or k == "filename":
                            arguments["path"] = v
                        elif k == "content" or k == "text" or k == "data":
                            arguments["content"] = v
                    if "content" not in arguments:
                        arguments["content"] = str(arguments)
            if not isinstance(arguments, dict):
                logger.warning(f"Arguments is not a dict for tool {func_name}: {type(arguments)}")
                # Hermes风格:收集ToolError
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error=f"TypeError: arguments must be dict, got {type(arguments).__name__}",
                    tool_result="Error: arguments must be a dict",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content="Error: arguments must be a dict",
                    is_error=True
                )

            # Strategy layer: pre-validate + remap deprecated names (e.g. search_web → web_search)
            from tools.strategy import pre_validate_tool_call, route_tool_call

            pre_result = pre_validate_tool_call(func_name, arguments)
            if not pre_result.ok:
                err_msg = pre_result.error_message or "pre_validation failed"
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error=err_msg,
                    tool_result=f"Error: {err_msg}",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"Error: {err_msg}",
                    is_error=True,
                )

            func_name, arguments, routing_error = route_tool_call(func_name, arguments)
            if routing_error:
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error=routing_error,
                    tool_result=f"Error: {routing_error}",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"Error: {routing_error}",
                    is_error=True,
                )

            # ── 统一 dispatch：通过 tools.registry.registry.dispatch() ──
            # dispatch() 返回 JSON 字符串，统一处理错误格式。
            # Sync handler 在线程池中运行以避免阻塞 event loop。
            entry = _tool_registry_module.registry._tools.get(func_name)
            if entry is not None and not entry.is_async:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    _tool_executor,
                    _tool_registry_module.registry.dispatch,
                    func_name,
                    arguments,
                )
            else:
                result = _tool_registry_module.registry.dispatch(func_name, arguments)

            # Plugin hook: post_tool_call
            # 在工具调用后执行
            try:
                self._invoke_hook(
                    "post_tool_call",
                    tool_name=func_name,
                    result=str(result),
                )
            except Exception as e:
                logger.warning(f"post_tool_call hook failed: {e}")

            # 触发tool_complete_callback
            if self.tool_complete_callback:
                try:
                    self.tool_complete_callback(func_name, str(result))
                except Exception as e:
                    logger.warning(f"tool_complete_callback error: {e}")

            # 软心跳记录
            try:
                import subprocess, os, time
                _start = getattr(self, '_tool_start_time', {}).pop(func_name, time.time())
                _dur = (time.time() - _start) * 1000
                _hb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'heartbeat', 'soft_beat.py')
                subprocess.Popen([sys.executable, _hb_path, func_name, str(_dur), 'OK'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            return ToolResult(
                tool_call_id=tool_call_id,
                content=str(result),
                is_error=False
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_call['name']}, error: {e}")
            # Hermes风格:收集ToolError
            self._tool_errors.append(ToolError(
                turn=turn,
                tool_name=func_name,
                arguments=str(raw_args)[:200],
                error=f"{type(e).__name__}: {e}",
                tool_result="Error: tool execution failed",
            ))

            # 触发tool_complete_callback(错误情况)
            if self.tool_complete_callback:
                try:
                    self.tool_complete_callback(func_name, f"Error: {e}")
                except Exception:
                    pass

            # 软心跳记录(错误)
            try:
                import subprocess, os, time
                _start = getattr(self, '_tool_start_time', {}).pop(func_name, time.time())
                _dur = (time.time() - _start) * 1000
                _hb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'heartbeat', 'soft_beat.py')
                subprocess.Popen([sys.executable, _hb_path, func_name, str(_dur), 'FAIL', str(e)[:100]], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            return ToolResult(
                tool_call_id=tool_call["id"],
                content="Error: tool execution failed",
                is_error=True
            )


    def build_system_prompt(self) -> str:
        """构建系统提示"""
        return self.system_prompt

    # ========================================================================
    # Skill自进化机制
    # ========================================================================

    async def execute_skill(self, skill_name: str, **kwargs) -> Any:
        """
        执行Skill(自进化核心)

        Args:
            skill_name: Skill名称
            **kwargs: Skill参数

        Returns:
            Skill执行结果
        """
        try:
            result = await self.skill_manager.execute_skill(skill_name, **kwargs)
            logger.info(f"Skill执行成功: {skill_name}")
            return result
        except Exception as e:
            logger.error(f"Skill执行失败: {skill_name}, error: {e}")
            raise

    async def evolve_skill(self, skill_name: str, new_handler: Callable) -> bool:
        """
        进化Skill(基于执行结果学习)

        Args:
            skill_name: Skill名称
            new_handler: 新的处理函数

        Returns:
            是否进化成功
        """
        result = await self.skill_manager.evolve_skill(skill_name, new_handler)
        if result:
            logger.info(f"Skill进化成功: {skill_name}")
        return result

    def register_skill(
        self,
        name: str,
        description: str,
        handler: Callable,
        schema: Dict[str, Any],
        category: str = "general",
        tags: List[str] = None,
        version: str = "1.0.0",
        author: str = "MimirAether"
    ) -> bool:
        """
        注册新Skill

        Args:
            name: Skill名称
            description: Skill描述
            handler: Skill处理函数
            schema: Skill参数schema
            category: Skill分类
            tags: 标签列表
            version: 版本号
            author: 作者

        Returns:
            是否注册成功
        """
        return self.skill_manager.register_skill(
            name=name,
            description=description,
            handler=handler,
            schema=schema,
            category=category,
            tags=tags,
            version=version,
            author=author
        )

    def get_skill_stats(self) -> Dict[str, Any]:
        """
        获取Skill统计信息

        Returns:
            统计信息字典
        """
        return self.skill_manager.get_statistics()

    def list_skills(self, category: str = None) -> List:
        """
        列出Skills

        Args:
            category: 按分类过滤

        Returns:
            Skill列表
        """
        return self.skill_manager.list_skills(category=category)

    # ========================================================================
    # 轨迹记录
    # ========================================================================

    def _start_trajectory(self):
        """开始轨迹记录"""
        self._trajectory = []

    def _save_trajectory(self, completed: bool):
        """保存轨迹"""
        if not self.save_trajectories:
            return

        # 实现轨迹保存到JSONL
        from datetime import datetime
        import re

        # 敏感信息过滤正则(覆盖多种凭证格式)
        SENSITIVE_PATTERNS = re.compile(
            r'(api_key|apiKey|api-key|token|auth|bearer|password|passwd|secret|credential|private_key|privatekey|ssh-rsa'
            r'|-----BEGIN [A-Z0-9 ]+-----[\s\S]+?-----END [A-Z0-9 ]+-----|'
            r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|'
            r'AKIA[0-9A-Z]{16}|'
            r'ghp_[a-zA-Z0-9]{36}|'
            r'sk-[a-zA-Z0-9]{48}|'
            r'#[a-f0-9]{32})',  # Generic 32-char hex (common secret format)
            re.IGNORECASE
        )

        def mask_sensitive(text: str) -> str:
            """过滤敏感信息"""
            if not text:
                return text
            # 将敏感词替换为[REDACTED]
            return SENSITIVE_PATTERNS.sub(r'[REDACTED]', text)

        # 将Message对象转换为dict以支持JSON序列化
        def msg_to_dict(msg: Message) -> dict:
            result = {"role": msg.role.value, "content": mask_sensitive(msg.content)}
            if msg.name:
                result["name"] = msg.name
            if msg.tool_call_id:
                result["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                # 过滤tool_calls中的敏感信息
                masked_tool_calls = []
                for tc in msg.tool_calls:
                    masked_tc = dict(tc)
                    if 'function' in masked_tc and 'arguments' in masked_tc['function']:
                        masked_tc['function']['arguments'] = mask_sensitive(str(masked_tc['function']['arguments']))
                    masked_tool_calls.append(masked_tc)
                result["tool_calls"] = masked_tool_calls
            return result

        entry = {
            "id": str(uuid.uuid4()),
            "model": self.model,
            "timestamp": datetime.now().isoformat(),
            "completed": completed,
            "conversations": [msg_to_dict(m) for m in self.conversation_history],
        }

        # 保存到文件(使用绝对路径)
        import os
        trajectory_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trajectory")
        os.makedirs(trajectory_dir, exist_ok=True)
        trajectory_file = os.path.join(trajectory_dir, f"trajectory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        try:
            with open(trajectory_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # 设置文件权限为600(仅所有者读写)
            os.chmod(trajectory_file, 0o600)
            logger.info(f"Trajectory saved to {trajectory_file}")
        except Exception as e:
            logger.error(f"Failed to save trajectory: {e}")

    async def reset(self):
        """重置Agent状态"""
        self.conversation_history = []
        self.budget = IterationBudget(self.max_iterations)
        self._trajectory = []
        self.compressor.reset_history()
        logger.info("Agent reset")

    def _restore_session(self, session_id: str = None) -> bool:
        """委托给当前 ``session_backend``（默认 :class:`_BuiltinSessionRestore`）。"""
        return self._session_backend.restore_after_init(session_id)

    def _builtin_restore_session(self, session_id: str = None) -> bool:
        """
        内置：从 SessionDB 恢复会话

        学习自Hermes会话持久化:
        - 从Hermes SessionDB恢复消息历史
        - 恢复conversation_history

        Args:
            session_id: 要恢复的session ID(可选)

        Returns:
            是否成功恢复
        """
        try:
            db = self._session_db_factory.create_session_db()
            if db is None:
                return False

            # 如果没有指定session_id,尝试获取最近的
            if not session_id:
                # 获取最近一次session
                sessions = db.export_all()
                if not sessions:
                    logger.debug("No sessions found in SessionDB")
                    return False
                # 取最新的session
                latest = sessions[-1] if sessions else None
                if latest:
                    session_id = latest.get('session_id')

            if not session_id:
                return False

            # 获取session消息
            messages = db.get_messages(session_id)
            if not messages:
                logger.debug(f"No messages found for session {session_id}")
                return False

            # 转换为conversation_history
            restored_count = 0
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content', '')

                if role == 'user':
                    self.conversation_history.append(Message(
                        role=MessageRole.USER,
                        content=content
                    ))
                    restored_count += 1
                elif role == 'assistant':
                    tool_calls = msg.get('tool_calls')
                    self.conversation_history.append(Message(
                        role=MessageRole.ASSISTANT,
                        content=content,
                        tool_calls=tool_calls
                    ))
                    restored_count += 1
                elif role == 'tool':
                    self.conversation_history.append(Message(
                        role=MessageRole.TOOL,
                        content=content,
                        tool_call_id=msg.get('tool_call_id')
                    ))
                    restored_count += 1

            if restored_count > 0:
                logger.info(f"Restored {restored_count} messages from session {session_id}")
                return True

        except Exception as e:
            logger.warning(f"Failed to restore session: {e}")

        return False

    # ========================================================================
    # Plugin Hook系统(学习自Hermes)
    # ========================================================================

    # 支持的Hook类型
    VALID_HOOKS = {
        "pre_llm_call",      # LLM调用前
        "post_llm_call",     # LLM调用后
        # "pre_tool_call" 已移除 - 曾导致无限循环bug
        "post_tool_call",     # 工具调用后
        "on_session_start",    # 会话开始
        "on_session_end",     # 会话结束
    }

    def _invoke_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """
        调用指定名称的所有Hook

        学习自Hermes invoke_hook:
        - 查找所有注册的hook函数
        - 按顺序执行
        - 返回所有hook的返回结果
        """
        if hook_name not in self.VALID_HOOKS:
            logger.warning(f"Unknown hook: {hook_name}")
            return []

        hooks = getattr(self, f"_{hook_name}_hooks", [])
        results = []
        for hook_func in hooks:
            try:
                result = hook_func(**kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(f"Hook {hook_name} failed: {e}")
        return results

    def register_hook(self, hook_name: str, hook_func: callable) -> None:
        """
        注册一个Hook函数

        Args:
            hook_name: Hook名称(如"pre_llm_call")
            hook_func: Hook函数
        """
        if hook_name not in self.VALID_HOOKS:
            raise ValueError(f"Unknown hook: {hook_name}")

        attr_name = f"_{hook_name}_hooks"
        if not hasattr(self, attr_name):
            setattr(self, attr_name, [])
        getattr(self, attr_name).append(hook_func)
        logger.debug(f"Registered hook: {hook_name}")

    def _try_activate_fallback(self) -> bool:
        """
        尝试激活Fallback模型

        学习自Hermes fallback机制:
        - 当主模型API失败时,尝试使用fallback模型
        - 需要配置fallback_model
        """
        if not self.fallback_model:
            return False

        if self._fallback_activated:
            logger.debug("Fallback already activated, not trying again")
            return False

        try:
            fallback = self.fallback_model
            self.model = fallback.get("model", self.model)
            self._fallback_activated = True
            self._emit_status(f"🔄 Activating fallback model: {self.model}")
            logger.info(f"Fallback activated: {self.model}")
            return True
        except Exception as e:
            logger.warning(f"Failed to activate fallback: {e}")
            return False

    def _restore_primary_runtime(self) -> None:
        """
        恢复主运行时(Fallback后)

        学习自Hermes:
        - 在新的对话轮次开始时,如果上次使用了fallback,尝试恢复主模型
        - 只有当_fallback_activated为True时才恢复
        """
        if not self._fallback_activated:
            return

        if self._primary_model and self.model != self._primary_model:
            self.model = self._primary_model
            self._fallback_activated = False
            self._emit_status(f"✅ Restored primary model: {self.model}")
            logger.info(f"Primary runtime restored: {self.model}")


# 导出的类和函数
__all__ = [
    "MimirAetherAgent",
    "Message",
    "MessageRole",
    "ToolCall",
    "ToolResult",
    "Plan",
    "ExecutionResult",
    "IterationBudget",
    "ToolRegistry",
]


# 技能函数已迁移到 agent/skill_funcs.py
# 导入已在上方完成，保持向后兼容
