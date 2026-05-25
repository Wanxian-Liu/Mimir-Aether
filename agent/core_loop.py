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
import copy
import functools
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
from .context_compressor import ContextCompressor, CompressionResult, MimirContextCompressor
from .insights import InsightsEngine, MetricType
from memory.fencing import MemoryFencer
from skills.skill_manager import SkillManager, SkillStatus

# 自我进化模块：多层次错误恢复 & 增强迭代预算
from .recovery import (
    MultiLevelRecovery, RecoveryContext, RecoveryStats, RecoveryLevel,
    get_recovery, set_recovery
)
from .decision_ring import DecisionRing, DecisionRingConfig, DecisionResult
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
    from mimir_state import SessionDB
except ImportError:
    SessionDB = None

# 集成新模块
from . import prompt_builder
from . import model_metadata
from . import anthropic_adapter

# 集成凭证池模块
from . import credential_pool
from .credential_pool import CredentialPool, PooledCredential, create_credential
from .smart_model_routing import resolve_turn_route
# Async bridge: persistent event loops for safe sync-tool dispatch.
# Imported from agent/async_bridge.py (Hermes pattern).
# _tool_executor, resize_tool_pool, get_tool_loop, get_worker_loop
from .async_bridge import (
    get_tool_executor,
    resize_tool_pool,
    get_tool_loop,
    get_worker_loop,
    run_async,
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
from .recovery_mixin import RecoveryMixin
from .exec_mixin import ExecMixin, _BuiltinToolBackend
from .callers_mixin import CallersMixin, _BuiltinLlmBackend
from .config_mixin import ConfigMixin


logger = logging.getLogger(__name__)


# ── DEPRECATED since d4 P0-1: migrated to agent/tools/repair.repair_write_file_args ──
# Redirecting for backward compatibility with any external callers.
# Remove after 2026Q3 if unused.
def _parse_write_file_arguments_string(raw_args: str) -> Optional[Dict[str, Any]]:
    """[DEPRECATED] → agent.tools.repair.repair_write_file_args"""
    from .tools.repair import repair_write_file_args
    return repair_write_file_args(raw_args)


# ── DEPRECATED P1-4: IterationBudget = alias(EnhancedIterationBudget) ──
# Provided at line 87 via iteration_budget module import; this redundant
# module-level import kept for legacy scripts that import from core_loop directly.
# New code: from .iteration_budget import EnhancedIterationBudget
from .iteration_budget import IterationBudget as _IterationBudget_Compat  # noqa: F401




# ── 工具注册表已统一到 tools/registry.py（Hermes 模式） ──
# 本地 ToolRegistry 兼容层：委托到真正的 tools.registry.registry
# ⚠️ DEPRECATED: 新代码应直接使用 tools.registry.registry 而非此兼容层。
# 保留仅用于 agent/server.py 和 agent/__init__.py 向后兼容导出。
import tools.registry as _tool_registry_module


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


class MimirAetherAgent(RecoveryMixin, ExecMixin, CallersMixin, ConfigMixin):
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
        enabled_toolsets: list = None,
        disabled_toolsets: list = None,
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
        self.enabled_toolsets = enabled_toolsets or []
        self.disabled_toolsets = disabled_toolsets or []
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
        # 工具注册已统一到 tools.registry.registry（Hermes 模式）
        # 不再需要本地兼容层；直接使用全局 registry
        
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
        self.max_history_length = 200  # 对齐 1M 上下文 (200条×~5K=~1M tokens)

        # 初始化凭证池(先于compressor — 获取context_length需要API key/base_url)
        self._credential_pool: Optional[CredentialPool] = None
        self._init_credential_pool()

        # 获取模型真实context_length (DeepSeek V4 Pro = 1M)
        self._context_length = model_metadata.get_model_context_length(
            model=model,
            base_url=self._get_model_base_url(),
            api_key=self._get_api_key(),
        )

        # P0-2: 错误决策环 — 须在 _context_length 就绪后构造
        self.decision_ring = DecisionRing(
            DecisionRingConfig(
                max_retries=3,
                max_context_size=self._context_length or 1048576,
            )
        )

        # MimirAether 自研上下文压缩器（context_length 构造即正确，不依赖事后修正）
        self.compressor = MimirContextCompressor(
            model=model,
            context_length=int(self._context_length or 1048576),
            threshold_percent=0.50,  # 500K主动压缩, 1M硬天花板
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

    async def chat(self, message: str) -> str:
        """
        主聊天接口

        处理单条用户消息,返回助手响应
        """
        # 运行对话(消息添加由run_conversation统一管理)
        response = await self.run_conversation(message)

        return response

    async def run_conversation(
        self, user_message: str,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> str:
        """
        完整对话运行

        学习自Hermes run_conversation:
        - 构建消息列表(每次迭代重建)
        - 调用模型API(带超时控制)
        - 处理工具调用
        - 管理迭代预算
        
        Args:
            user_message: 当前用户消息
            conversation_history: 前置对话历史（从gateway transcript加载）
                gateway格式: [{"role": "user"|"assistant"|"tool", "content": ..., ...}, ...]
                仅有 {"role", "content"} 键的消息（纯文本user/assistant）会被注入。
                包含 tool_calls/tool_call_id 的复杂消息被跳过（Mimir本身不管理工具序列）。
        """
        # 生成会话ID(用于Insights追踪)
        session_id = str(uuid.uuid4())
        
        # 暴露 SESSION_ID 给工具层: execute_code/terminal/session_search
        # 等工具可通过 os.environ 获知自己所属 session
        # 同时设置 HERMES_SESSION_ID 以兼容继承的 Hermes 工具链
        os.environ["MIMIR_SESSION_ID"] = session_id
        os.environ["HERMES_SESSION_ID"] = session_id
        
        # 开始轨迹记录
        if self.save_trajectories:
            self._start_trajectory()
        
        # ── 注入前置对话历史（C1 飞书对话体验） ──
        # 从gateway transcript加载的历史消息，仅注入纯文本user/assistant轮次
        # 含 tool_calls 或 tool 角色的消息被跳过（Mimir自行管理工具调用）
        # 受 context.max_recent_messages 限制，只取最近 N 条（默认25）
        if conversation_history:
            # 加载配置中的 max_recent_messages（默认25）
            _max_recent = 25
            try:
                import yaml as _yaml
                _cfg_path = get_mimir_home() / "config.yaml"
                if _cfg_path.exists():
                    with open(_cfg_path, encoding="utf-8") as _f:
                        _cfg = _yaml.safe_load(_f) or {}
                    _max_recent = int(
                        (_cfg.get("context") or {}).get("max_recent_messages", 25)
                    )
            except Exception:
                pass

            # 截断到最近 N 条（在过滤前截断以保留最近的有效消息）
            _history_slice = conversation_history
            if len(conversation_history) > _max_recent:
                _history_slice = conversation_history[-_max_recent:]

            injected = 0
            for hmsg in _history_slice:
                role = hmsg.get("role", "")
                if role not in ("user", "assistant"):
                    continue
                content = hmsg.get("content", "")
                if not content:
                    continue
                if "tool_calls" in hmsg or "tool_call_id" in hmsg:
                    # P0-3 设计权衡：C1 跳过 tool 消息是有意设计。
                    # 原因：保留过时的 tool_calls/tool_results 会误导模型使用错误的
                    # tool_call_id 调用工具。Mimir 自行管理工具调用链路，
                    # 不依赖历史 tool 状态作为决策依据。
                    # 边界条件：如果用户明确引用历史工具输出（如"上次那个结果"），
                    # 模型当前无法访问该上下文——这是已知局限性，非 bug。
                    continue
                # 跳过系统提示类消息（gateway可能注入）
                if role == "assistant" and content.startswith("["):
                    if content.startswith("[System") or content.startswith("[Gateway"):
                        continue
                msg = Message(
                    role=MessageRole.USER if role == "user" else MessageRole.ASSISTANT,
                    content=content
                )
                msg._c1_injected = True  # P0-4: 标记C1注入，compressor跳过计数
                self.conversation_history.append(msg)
                injected += 1
            if injected:
                _total = len(conversation_history)
                _limit_info = f" (limit={_max_recent})" if _total > _max_recent else ""
                logger.info(
                    f"[C1] Injected {injected} prior messages from conversation_history "
                    f"(total={_total}, skipped={_total - injected} non-text){_limit_info}"
                )

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
        # 重置中断标志，防止上次会话残留
        self._interrupt_requested = False
        self._interrupt_message = None
        
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

        # 限制历史长度,防止内存耗尽（保完整 tool pair）
        if len(self.conversation_history) > self.max_history_length:
            system_msgs = [m for m in self.conversation_history if m.role == MessageRole.SYSTEM]
            other_msgs = [m for m in self.conversation_history if m.role != MessageRole.SYSTEM]
            # 在 other_msgs 中找到安全的 tool pair 边界
            temp_history = self.conversation_history
            self.conversation_history = other_msgs  # 临时替换以复用 _find_safe_truncation_boundary
            boundary = self._find_safe_truncation_boundary(self.max_history_length)
            self.conversation_history = temp_history  # 恢复
            self.conversation_history = system_msgs + other_msgs[boundary:]
            logger.debug(
                f"History trimmed: kept {len(self.conversation_history)} "
                f"(safe boundary at other_msgs[{boundary}])"
            )
            # 截断后清理孤儿 tool 对，防止 400 错误
            self._clean_orphan_tools()

        # 断点续传:用于跟踪当前步骤
        _current_step = checkpoint.current_step if checkpoint else 0

        try:
            # 恢复主运行时(Fallback后)
            self._restore_primary_runtime()

            # ── 委托给 MimirAgentLoop (Hermes 微内核模式) ──
            # 构建消息列表
            _loop_messages = self._build_full_messages()
            
            # 预压缩一次（MimirAgentLoop 内部不做压缩）
            if self.compressor.needs_compression(_loop_messages):
                if self.compressor.has_content_to_compress(_loop_messages):
                    _loop_messages, _ = await self.compressor.compress(_loop_messages)
            
            # 构建 tool schemas + valid names
            from tools.toolsets import resolve_enabled_tools
            _tool_names = resolve_enabled_tools(
                self.enabled_toolsets or None,
                disabled=self.disabled_toolsets or None,
            )
            import tools.registry as _tool_registry_module
            _tool_schemas = _tool_registry_module.registry.get_definitions(set(_tool_names))
            _valid_names = set(_tool_names)
            
            # ── model_call 适配器 ──
            async def _model_call_adapter(msgs):
                try:
                    _resp, _lat = await asyncio.wait_for(
                        self._call_model_with_tokens(msgs, session_id),
                        timeout=3600.0,
                    )
                except asyncio.TimeoutError:
                    return None
                except Exception as _e:
                    _err_str = str(_e)
                    _err_lower = _err_str.lower()
                    is_orphan = (
                        "tool' must be a response" in _err_str
                        or "tool must be a response" in _err_str
                        or ("tool_calls" in _err_lower and "tool" in _err_lower)
                        or ("model api request failed: 400" in _err_lower
                            and ("tool" in _err_lower or "(empty body)" in _err_lower))
                    )
                    if is_orphan:
                        logger.warning("Orphan tool cleanup triggered in adapter")
                        # Orphan cleanup logic preserved
                        self._clean_orphan_tools()
                        return None
                    # P0-2: DecisionRing → MultiLevelRecovery 双轨错误处理
                    _decision = self.decision_ring.decide(
                        _e, provider=self.model.split("/")[0] if "/" in self.model else "",
                        model=self.model,
                    )
                    logger.debug(
                        "DecisionRing: %s retryable=%s fallback=%s backoff=%.1fs",
                        _decision.classified_error.reason.value if _decision.classified_error.reason else "unknown",
                        _decision.should_retry,
                        _decision.should_fallback,
                        _decision.backoff_seconds,
                    )
                    await self.handle_error_with_recovery(_e)
                    return None
                self._compressor_sync_usage_from_llm(_resp, msgs)
                if _resp.get("tool_calls"):
                    _resp["tool_calls"] = self._deduplicate_tool_calls(_resp["tool_calls"])
                return _resp
            
            # ── tool_dispatcher 适配器 ──
            def _tool_dispatcher_adapter(name, args, task_id):
                import json as _json
                tc = {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {"name": name, "arguments": _json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)},
                }
                result = run_async(self._execute_single_tool(tc, turn=self._current_turn))
                return result.content
            
            # ── 创建并运行 MimirAgentLoop ──
            _loop = MimirAgentLoop(
                model_call=_model_call_adapter,
                tool_schemas=_tool_schemas,
                valid_tool_names=_valid_names,
                tool_dispatcher=_tool_dispatcher_adapter,
                max_turns=self.max_iterations,
                task_id=task_id,
                interrupt_check=lambda: self._interrupt_requested,
            )
            _result = await _loop.run(_loop_messages)

            # MimirAgentLoop owns turn iteration; sync legacy budget for TurnManager/checkpoints.
            for _ in range(int(_result.turns_used or 0)):
                if not await self.budget.consume():
                    break

            # ── 从 AgentResult 提取结果 ──
            self._tool_errors = [ToolError(
                turn=e.turn, tool_name=e.tool_name,
                arguments=e.arguments, error=e.error, tool_result=e.tool_result,
            ) for e in _result.tool_errors]
            self._reasoning_per_turn = _result.reasoning_per_turn
            
            # 同步 conversation_history（MimirAgentLoop 修改的是 messages，需要回写）
            if _result.messages and len(_result.messages) > 0:
                _new_history = []
                for _md in _result.messages:
                    _role_str = _md.get("role", "")
                    if _role_str == "system":
                        continue
                    _mrole = MessageRole(_role_str) if _role_str in ("user","assistant","tool") else None
                    if _mrole is None:
                        continue
                    _new_history.append(Message(
                        role=_mrole,
                        content=_md.get("content", ""),
                        tool_calls=_md.get("tool_calls"),
                        tool_call_id=_md.get("tool_call_id"),
                        reasoning_content=_md.get("reasoning_content"),
                    ))
                self.conversation_history = [self.conversation_history[0]] + _new_history
            
            # 提取最终文本响应
            _final_content = ""
            for _md in reversed(_result.messages):
                if _md.get("role") == "assistant" and _md.get("content"):
                    _final_content = _md.get("content", "")
                    break
            
            if _result.interrupted:
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
            
            try:
                self._invoke_hook(
                    "on_session_end",
                    session_id=session_id,
                    response=_final_content,
                )
            except Exception as e:
                logger.warning(f"on_session_end hook failed: {e}")
            
            _final_content = self._strip_think_blocks(_final_content)
            return _final_content
        finally:
            checkpoint_mgr.clear_checkpoint(task_id)

            # 保存轨迹
            if self.save_trajectories:
                self._save_trajectory(completed=True)

            # 跨会话记忆结束：自动执行 curator 胶囊化
            # ============================================================
            if self._cross_memory is not None:
                try:
                    self._cross_memory.end_session()
                    self._cross_memory.save()
                except Exception as e:
                    logger.warning(f'[CrossSession] End session failed: {e}')

            # B3 自进化闭环：session 结束时的健康快照
            # ============================================================
            try:
                from agent.monitor_collector import get_monitor
                monitor = get_monitor()
                # 记录 session 结束事件
                monitor.metrics.increment("sessions_completed")
                report = monitor.quick_check()
                logger.info(
                    "[B3闭环] Session health snapshot: status=%s anomalies=%d",
                    report.status.value, len(report.anomalies),
                )
                if report.anomalies:
                    for a in report.anomalies:
                        logger.warning("[B3闭环] Anomaly: %s | %s", a.metric_name, a.message)
            except Exception as e:
                logger.debug("[B3闭环] Health check unavailable: %s", e)

    def set_session_backend(self, backend: SessionRestorePort) -> None:
        """运行时切换会话恢复后端（须实现 :class:`~agent.session_port.SessionRestorePort`）。"""
        self._session_backend = backend

    def set_session_db_factory(self, factory: SessionDbClientFactory) -> None:
        """运行时切换 SessionDB 工厂（影响后续 ``create_session_db``；已构造的 ``insights`` 不变）。"""
        self._session_db_factory = factory

    def set_checkpoint_backend(self, backend: CheckpointPersistencePort) -> None:
        """运行时切换检查点后端（须实现 :class:`~agent.checkpoint_port.CheckpointPersistencePort`）。"""
        self._checkpoint_backend = backend

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
        """保存轨迹（legacy：写入 repo 下 trajectory/；SoT 见 ADR-005 ExecutionRecorder）。"""
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
        self.budget = EnhancedIterationBudget(self.max_iterations)  # P1-4: 使用增强类
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

