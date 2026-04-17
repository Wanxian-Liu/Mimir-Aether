"""
MimirAether Agent Core Loop

学习自Hermes AIAgent架构，重新实现的核心Agent类。

核心功能：
- 主对话循环
- 工具调用处理
- 上下文管理
- 迭代预算控制

集成模块：
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
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Union
from enum import Enum

# 新模块导入
from .context_compressor import ContextCompressor, CompressionResult
from .insights import InsightsEngine, MetricType
from memory.fencing import MemoryFencer
from skills.skill_manager import SkillManager, SkillStatus

# 导入Hermes SessionDB用于数据持久化
import sys
from pathlib import Path

# 添加MimirAether路径（优先）
mimir_root = Path.home() / ".openclaw" / "projects" / "MimirAether"
mimir_path = str(mimir_root)
if mimir_path not in sys.path:
    sys.path.insert(0, mimir_path)

# 添加Hermes路径（用于SessionDB，放在MimirAether之后）
hermes_path = str(Path.home() / ".openclaw" / "projects" / "hermes-agent")
if hermes_path not in sys.path:
    sys.path.append(hermes_path)

try:
    from hermes_state import SessionDB
except ImportError:
    SessionDB = None

# 集成新模块
from . import prompt_builder
from . import model_metadata
from . import anthropic_adapter

# 集成凭证池模块
from . import credential_pool
from .credential_pool import CredentialPool, PooledCredential, create_credential

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: Union[str, Dict[str, Any]]


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Plan:
    """任务分解计划"""
    task: str
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    complexity: int = 0
    estimated_time: int = 0


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    tool_calls_made: int = 0
    duration: float = 0.0


class IterationBudget:
    """
    迭代预算控制器
    
    学习自Hermes IterationBudget：
    - 父Agent默认90次迭代
    - 子Agent默认50次迭代
    - execute_code等工具调用不消耗预算
    """
    
    def __init__(self, max_total: int = 90):
        self.max_total = max_total
        self._used = 0
        self._lock = asyncio.Lock()
    
    async def consume(self) -> bool:
        """尝试消耗一次迭代"""
        async with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True
    
    async def refund(self) -> None:
        """退还一次迭代（如execute_code）"""
        async with self._lock:
            if self._used > 0:
                self._used -= 1
    
    async def get_remaining(self) -> int:
        """获取剩余迭代次数（异步安全）"""
        async with self._lock:
            return self.max_total - self._used


class ToolRegistry:
    """
    工具注册表
    
    提供工具注册和调用功能
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict] = {}
    
    def register(self, name: str, func: Callable, schema: Dict):
        """注册工具"""
        # 基础schema校验
        if not isinstance(schema, dict):
            raise ValueError(f"Invalid schema type for tool {name}: expected dict")
        if "parameters" not in schema:
            raise ValueError(f"Invalid schema for tool {name}: missing 'parameters' field")
        
        self._tools[name] = func
        self._schemas[name] = schema
        logger.info(f"Registered tool: {name}")
    
    async def execute(self, name: str, arguments: Dict) -> Any:
        """执行工具"""
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")
        
        func = self._tools[name]
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {name}, error: {e}")
            raise
    
    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())
    
    def get_schema(self, name: str) -> Optional[Dict]:
        """获取工具schema"""
        return self._schemas.get(name)


class MimirAetherAgent:
    """
    MimirAether核心Agent类
    
    学习自Hermes AIAgent，重新实现的Agent主循环。
    
    核心接口：
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
        # Callback系统（学习自Hermes）
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
        
        # Callback系统（学习自Hermes）
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
        
        # Status callback（学习自Hermes _emit_status）
        self._status_message = ""  # 当前状态消息
        
        # Plugin hooks（学习自Hermes）
                # Plugin hooks（学习自Hermes）
        for hook_name in self.VALID_HOOKS:
            setattr(self, f"_{hook_name}_hooks", [])
        
        # 初始化组件
        self.budget = IterationBudget(max_iterations)
        self.tool_registry = ToolRegistry()
        self.conversation_history: List[Message] = []
        self.max_history_length = 100  # 对话历史最大长度，防止内存耗尽

        # 新模块初始化
        self.compressor = ContextCompressor()
        
        # 初始化SessionDB并传入InsightsEngine（SQL模式）
        _db = None
        if SessionDB is not None:
            try:
                _db = SessionDB()
            except Exception:
                pass
        self.insights = InsightsEngine(_db) if _db else InsightsEngine()
        
        # 初始化SkillManager（自进化核心）
        self.skill_manager = SkillManager()
        
        self.fencer = MemoryFencer()

        # 初始化凭证池（在使用_get_api_key之前）
        self._credential_pool: Optional[CredentialPool] = None
        self._init_credential_pool()

        # 初始化model_metadata获取context_length
        self._context_length = model_metadata.get_model_context_length(
            model=model,
            base_url=self._get_model_base_url(),
            api_key=self._get_api_key(),
        )

        # 初始化prompt_builder构建系统提示
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = self._build_system_prompt()

        # 轨迹记录
        self._trajectory: List[Dict] = []
        
        # 工具调用并发限制（最多同时执行5个工具）
        self._tool_semaphore = asyncio.Semaphore(5)
        
        # 中断机制（学习自Hermes）
        self._interrupt_requested = False
        self._interrupt_message = None
        self._execution_thread_id = threading.get_ident()
        
        # 注册内置工具
        self._register_builtin_tools()
        
        logger.info(f"MimirAether initialized with model: {model}, context_length: {self._context_length}")
        
        # 尝试从SessionDB恢复最近的session
        self._restore_session()
    
    def _emit_status(self, message: str) -> None:
        """
        发送状态消息到status_callback
        
        学习自Hermes _emit_status：
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
            # 如果没有callback但不是quiet模式，打印状态
            print(f"\n📍 {message}")
    
    def _emit_interim_assistant(self, content: str) -> None:
        """
        发送临时助手响应（流式输出时的中间响应）
        
        学习自Hermes：
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
    
    def _get_api_key(self) -> str:
        """获取当前模型的API key"""
        # Moonshot/Kimi系列 使用MOONSHOT_API_KEY环境变量
        if self.model.startswith("kimi-k2") or self.model.startswith("moonshot"):
            return os.environ.get("MOONSHOT_API_KEY", "")
        
        # DeepSeek优先使用DEEPSEEK_API_KEY
        if "deepseek" in self.model.lower():
            return os.environ.get("DEEPSEEK_API_KEY", "")
        
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
            return "https://api.moonshot.cn"  # 不要加/v1，会在API调用时拼接
        
        model_lower = self.model.lower()
        if "deepseek" in model_lower:
            return "https://api.deepseek.com"
        elif "minimax" in model_lower:
            return os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")
        elif "anthropic" in model_lower or "claude" in model_lower:
            return os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        elif "openai" in model_lower or "gpt" in model_lower:
            return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        else:
            return "https://api.deepseek.com"
    
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
                skills_dir=skills_dir,
            )
            
            return system_prompt if system_prompt else self._default_system_prompt()
        except Exception as e:
            logger.warning(f"Failed to build system prompt with prompt_builder: {e}")
            return self._default_system_prompt()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        try:
            import sys
            from pathlib import Path
            
            # 将MimirAether根目录添加到path
            mimir_root = Path(__file__).parent.parent
            if str(mimir_root) not in sys.path:
                sys.path.insert(0, str(mimir_root))
            
            # 注册builtin工具
            from tools.builtin import get_tool_functions as get_builtin_functions
            from tools.builtin import get_all_tools as get_builtin_schemas
            
            builtin_functions = get_builtin_functions()
            builtin_schemas = get_builtin_schemas()
            
            for name, func in builtin_functions.items():
                schema = builtin_schemas.get(name, {})
                self.tool_registry.register(name, func, schema)
            
            # 注册MimirCore工具
            try:
                from tools.mimircore_tool import get_tool_functions as get_mimircore_functions
                from tools.mimircore_tool import TOOL_SCHEMAS as mimircore_schemas
                
                mimircore_functions = get_mimircore_functions()
                for name, func in mimircore_functions.items():
                    schema = mimircore_schemas.get(name, {})
                    self.tool_registry.register(name, func, schema)
                
                logger.info(f"Registered {len(builtin_functions)} builtin + {len(mimircore_functions)} mimircore tools")
            except ImportError as e:
                logger.warning(f"Failed to import mimircore tools: {e}")
                logger.info(f"Registered {len(builtin_functions)} builtin tools")
                
        except ImportError as e:
            logger.warning(f"Failed to import builtin tools: {e}")
        
        # 注册Skill工具（skill_view, skills_list, skill_manage）
        try:
            from skills.skills_loader import skill_view as _skill_view_func, skills_list as _skills_list_func
            from skills.skills_loader import skill_manage as _skill_manage_func
            
            self.tool_registry.register("skill_view", _skill_view_func, SKILL_TOOL_SCHEMAS.get("skill_view", {}))
            self.tool_registry.register("skills_list", _skills_list_func, SKILL_TOOL_SCHEMAS.get("skills_list", {}))
            self.tool_registry.register("skill_manage", skill_manage_func, SKILL_MANAGE_SCHEMA)
            
            logger.info("Registered skill tools: skill_view, skills_list, skill_manage")
        except ImportError as e:
            logger.warning(f"Failed to import skill tools: {e}")
    
    def _fire_stream_delta(self, text: str) -> None:
        """
        触发流式输出回调
        
        学习自Hermes _fire_stream_delta：
        - 处理段落分隔
        - 调用所有注册的流式回调
        - 记录流式输出的累积文本
        """
        # 如果需要段落分隔，在文本前添加
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
        
        学习自Hermes interrupt方法：
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
        
        学习自Hermes _strip_think_blocks：
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
    
    def _deduplicate_tool_calls(self, tool_calls: list) -> list:
        """
        去除重复的工具调用
        
        学习自Hermes _deduplicate_tool_calls：
        - 基于(tool_name, arguments)唯一性去重
        - 只保留第一个出现的重复调用
        """
        seen = set()
        unique = []
        for tc in tool_calls:
            # 获取工具名称和参数
            func = tc.get('function', {})
            name = func.get('name', '')
            arguments = func.get('arguments', '')
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
        
        学习自Hermes _repair_tool_call：
        1. 尝试小写
        2. 尝试标准化（下划线替代连字符/空格）
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
        
        学习自Hermes _cleanup_dead_connections：
        - 关闭死TCP连接，防止CLOSE-WAIT累积
        - 对于aiohttp，简化处理：关闭并重建session
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
        
        学习自Hermes _interruptible_streaming_api_call：
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
                        
                        # 解析delta
                        choices = chunk.get('choices', [])
                        if not choices:
                            continue
                        
                        delta = choices[0].get('delta', {})
                        
                        # 处理内容
                        if delta.get('content'):
                            text = delta['content']
                            content_parts.append(text)
                            # 如果没有累积的工具调用，流式输出
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
                        'finish_reason': finish_reason
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

You can call tools to accomplish tasks. Always provide clear, accurate responses."""
    
    async def chat(self, message: str) -> str:
        """
        主聊天接口
        
        处理单条用户消息，返回助手响应
        """
        # 运行对话（消息添加由run_conversation统一管理）
        response = await self.run_conversation(message)
        
        return response
    
    async def run_conversation(self, user_message: str) -> str:
        """
        完整对话运行
        
        学习自Hermes run_conversation：
        - 构建消息列表（每次迭代重建）
        - 调用模型API（带超时控制）
        - 处理工具调用
        - 管理迭代预算
        """
        # 生成会话ID（用于Insights追踪）
        session_id = str(uuid.uuid4())

        # 开始轨迹记录
        if self.save_trajectories:
            self._start_trajectory()

        # 用MemoryFencer隔离用户消息（防止注入）
        fenced_msg = self.fencer.fence(user_message)
        if fenced_msg.was_modified:
            logger.warning(f"User message modified by fencer: {fenced_msg.warnings}")

        # 添加用户消息到历史（使用隔离后的内容）
        self.conversation_history.append(Message(
            role=MessageRole.USER,
            content=fenced_msg.content
        ))
        
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
        
        # 限制历史长度，防止内存耗尽
        if len(self.conversation_history) > self.max_history_length:
            # 保留系统消息和最新的对话
            system_msgs = [m for m in self.conversation_history if m.role == MessageRole.SYSTEM]
            other_msgs = [m for m in self.conversation_history if m.role != MessageRole.SYSTEM]
            self.conversation_history = system_msgs + other_msgs[-self.max_history_length:]
        
        try:
            # 恢复主运行时（Fallback后）
            self._restore_primary_runtime()
            
            # 主循环
            while True:
                # 检查是否被中断
                if self._interrupt_requested:
                    logger.info("Conversation interrupted by user")
                    return f"对话已被中断。" + (f" 您的输入: {self._interrupt_message}" if self._interrupt_message else "")
                
                # 检查预算
                if not await self.budget.consume():
                    logger.warning("Iteration budget exhausted")
                    return "抱歉，任务迭代次数已达上限。"
                
                # 触发step_callback（每步执行后）
                if self.step_callback:
                    try:
                        self.step_callback()
                    except Exception as e:
                        logger.warning(f"step_callback error: {e}")
                
                # 每次迭代都重建消息列表（使用当前全部历史）
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
                # 在LLM调用前执行，允许插件注入上下文
                try:
                    pre_results = self._invoke_hook(
                        "pre_llm_call",
                        user_message=user_message,
                        conversation_history=list(messages),
                        model=self.model,
                    )
                    # 如果有hook返回结果，注入到用户消息
                    for result in pre_results:
                        if isinstance(result, dict) and result.get("context"):
                            context_text = str(result["context"])
                            if messages and messages[0].get("role") == "system":
                                messages[0] = {"role": "system", "content": messages[0].get("content", "") + "\n\n" + context_text}
                except Exception as e:
                    logger.warning(f"pre_llm_call hook failed: {e}")

                # 调用模型（带超时控制）
                try:
                    response, latency_ms = await asyncio.wait_for(
                        self._call_model_with_tokens(messages, session_id),
                        timeout=3600.0  # 1小时超时
                    )
                except asyncio.TimeoutError:
                    logger.error("Model call timed out")
                    return "抱歉，模型响应超时，请重试。"
                except Exception as e:
                    logger.error(f"Model call failed: {e}")
                    # 尝试激活Fallback模型
                    if self._try_activate_fallback():
                        # Fallback激活成功，重试当前迭代
                        continue
                    # 通用错误，不泄露内部细节
                    return "抱歉，模型调用失败，请稍后重试。"
                
                # 添加助手响应到历史（仅当有内容或tool_calls时）
                response_content = response.get("content") or ""
                response_tool_calls = response.get("tool_calls")
                if response_content or response_tool_calls:
                    self.conversation_history.append(Message(
                        role=MessageRole.ASSISTANT,
                        content=response_content,
                        tool_calls=response_tool_calls
                    ))
                
                # Plugin hook: post_llm_call
                # 在LLM调用后执行，允许插件处理响应
                try:
                    self._invoke_hook(
                        "post_llm_call",
                        response=response,
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"post_llm_call hook failed: {e}")
                
                # 检查是否有工具调用
                if response.get("tool_calls") and response_content:
                    # 同时有文本和工具调用：先执行工具，再继续生成响应
                    # 去重工具调用
                    unique_tool_calls = self._deduplicate_tool_calls(response["tool_calls"])
                    tool_results = await self._execute_tools(unique_tool_calls)
                    
                    # 添加工具结果到历史
                    for result in tool_results:
                        self.conversation_history.append(Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=result.tool_call_id
                        ))
                    
                    # 工具调用后 refund（只refund一次，无论多少工具）
                    await self.budget.refund()
                    
                    # 继续循环，让模型基于工具结果生成最终响应
                    continue
                
                if response.get("tool_calls"):
                    # 只有工具调用，没有文本：执行工具
                    # 去重工具调用
                    unique_tool_calls = self._deduplicate_tool_calls(response["tool_calls"])
                    tool_results = await self._execute_tools(unique_tool_calls)
                    
                    # 添加工具结果到历史
                    for result in tool_results:
                        self.conversation_history.append(Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=result.tool_call_id
                        ))
                    
                    # 工具调用后 refund（只refund一次，无论多少工具）
                    await self.budget.refund()
                    
                    # 继续循环（下次迭代会重建messages）
                    continue
                
                # 文本响应，结束
                # 去除Think Block
                response_content = self._strip_think_blocks(response_content)
                
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
            # 保存轨迹
            if self.save_trajectories:
                self._save_trajectory(completed=True)
    
    def _build_full_messages(self) -> List[Dict]:
        """构建完整消息列表（用于API调用）"""
        messages = []
        
        # 系统提示
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # 对话历史（从开始到最新，全部包含）
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
            messages.append(msg_dict)
        
        return messages
    
    async def _call_model_with_tokens(
        self, messages: List[Dict], session_id: str
    ) -> tuple[Dict, float]:
        """
        调用模型API并记录token使用

        Returns:
            (response_dict, latency_ms)
        """
        import time
        start = time.monotonic()

        import os
        import aiohttp

        # 获取API配置（支持多平台）
        # 优先级：1. 显式传入 2. 环境变量 3. 默认DeepSeek
        if hasattr(self, 'model') and self.model:
            model_name = self.model
        else:
            model_name = os.environ.get("LLM_MODEL", "deepseek-chat")
        
        # 检测使用哪个API
        # Moonshot/Kimi系列 使用MOONSHOT_API_KEY环境变量
        if "kimi-k2" in model_name or model_name.startswith("moonshot"):
            api_key = os.environ.get("MOONSHOT_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
            base_url = "https://api.moonshot.cn"  # 注意：不要加/v1，会在下面拼接
            is_anthropic = False
        elif "deepseek" in model_name.lower():
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            base_url = "https://api.deepseek.com"
            is_anthropic = False
        elif "minimax" in model_name.lower() or os.environ.get("MINIMAX_API_KEY"):
            api_key = os.environ.get("MINIMAX_API_KEY", "")
            base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")
            is_anthropic = False
        elif "anthropic" in model_name.lower() or "claude" in model_name.lower():
            api_key = os.environ.get("ANTHROPIC_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
            base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            is_anthropic = True
        else:
            # 默认DeepSeek
            api_key = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
            base_url = "https://api.deepseek.com"
            is_anthropic = False
        
        if not api_key:
            raise ValueError(f"API key not set for model {model_name}")

        # 使用model_metadata获取context_length，智能设置max_tokens
        context_length = model_metadata.get_model_context_length(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
        )
        
        # 获取工具schemas
        from tools.builtin import get_all_tools as get_builtin_schemas
        raw_schemas = get_builtin_schemas()
        tool_schemas = []
        for name, schema in raw_schemas.items():
            tool_schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": schema.get("description", f"Tool: {name}"),
                    "parameters": schema.get("parameters", {})
                }
            })
        
        # 添加mimircore工具schemas
        try:
            from tools.mimircore_tool import TOOL_SCHEMAS as mimircore_schemas
            for name, schema in mimircore_schemas.items():
                tool_schemas.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": schema.get("description", f"Tool: {name}"),
                        "parameters": schema.get("parameters", {})
                    }
                })
        except ImportError:
            pass
        
        # 获取max_tokens
        max_output_tokens = model_metadata.get_anthropic_max_output(model_name) if "claude" in model_name.lower() else 4096
        max_tokens = min(max_output_tokens, context_length // 4) if context_length else 4096
        
        # 如果有流式消费者且非Anthropic API，使用流式调用
        if self._has_stream_consumers() and not is_anthropic:
            return await self._stream_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model_name,
                messages=messages,
                tool_schemas=tool_schemas,
                max_tokens=max_tokens,
                temperature=0.7,
            )
        
        # 否则使用标准非流式调用（原有逻辑）
        
        # 检测使用哪个API
        # Moonshot/Kimi系列 使用MOONSHOT_API_KEY环境变量
        if "kimi-k2" in model_name or model_name.startswith("moonshot"):
            api_key = os.environ.get("MOONSHOT_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
            base_url = "https://api.moonshot.cn"  # 注意：不要加/v1，会在下面拼接
            is_anthropic = False
        elif "deepseek" in model_name.lower():
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            base_url = "https://api.deepseek.com"
            is_anthropic = False
        elif "minimax" in model_name.lower() or os.environ.get("MINIMAX_API_KEY"):
            api_key = os.environ.get("MINIMAX_API_KEY", "")
            base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")
            is_anthropic = False
        elif "anthropic" in model_name.lower() or "claude" in model_name.lower():
            api_key = os.environ.get("ANTHROPIC_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
            base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            is_anthropic = True
        else:
            # 默认DeepSeek
            api_key = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
            base_url = "https://api.deepseek.com"
            is_anthropic = False
        
        if not api_key:
            raise ValueError(f"API key not set for model {model_name}")

        # 使用model_metadata获取context_length，智能设置max_tokens
        context_length = model_metadata.get_model_context_length(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
        )
        
        # Anthropic API使用不同的端点和格式
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
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 构建请求体（OpenAI兼容格式）
        # 使用model_metadata获取合适的max_tokens
        max_output_tokens = model_metadata.get_anthropic_max_output(model_name) if "claude" in model_name.lower() else 4096
        max_tokens = min(max_output_tokens, context_length // 4) if context_length else 4096
        
        # 获取工具schemas并转换为OpenAI格式
        from tools.builtin import get_all_tools as get_builtin_schemas
        raw_schemas = get_builtin_schemas()
        
        # 转换为OpenAI tool格式
        tool_schemas = []
        for name, schema in raw_schemas.items():
            tool_schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": schema.get("description", f"Tool: {name}"),
                    "parameters": schema.get("parameters", {})
                }
            })
        
        # 添加mimircore工具schemas
        try:
            from tools.mimircore_tool import TOOL_SCHEMAS as mimircore_schemas
            for name, schema in mimircore_schemas.items():
                tool_schemas.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": schema.get("description", f"Tool: {name}"),
                        "parameters": schema.get("parameters", {})
                    }
                })
        except ImportError:
            pass
        
        # 转换model名为API接受的格式
        api_model_name = model_name
        if "deepseek" in model_name.lower():
            # DeepSeek API只接受 "deepseek-chat" 或 "deepseek-coder" 格式
            if "/" in model_name:
                api_model_name = model_name.split("/")[-1]
        elif "minimax" in model_name.lower():
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

        # 发送请求
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
                        # 记录错误详情用于调试
                        error_text = await response.text()
                        logger.warning(f"API call failed: {response.status}, response: {error_text[:500]}")
                        raise RuntimeError(f"Model API request failed: {response.status}")

                    result = await response.json()

                    # 安全提取助手响应（边界检查）
                    choices = result.get("choices")
                    if not choices or len(choices) == 0:
                        raise RuntimeError("Invalid API response: no choices")

                    assistant_message = choices[0].get("message")
                    if not assistant_message:
                        raise RuntimeError("Invalid API response: no message in choice")

                    content = assistant_message.get("content") or ""
                    tool_calls = assistant_message.get("tool_calls")

                    # 提取usage信息（记录token）
                    usage = result.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    # 用InsightsEngine记录token使用
                    if prompt_tokens > 0:
                        self.insights.record(
                            MetricType.TOKEN_INPUT,
                            float(prompt_tokens),
                            metadata={
                                "session_id": session_id,
                                "platform": self.platform,
                                "model": self.model,
                            }
                        )
                    if completion_tokens > 0:
                        self.insights.record(
                            MetricType.TOKEN_OUTPUT,
                            float(completion_tokens),
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
                        "tool_calls": tool_calls
                    }, latency_ms
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                # 标记当前凭证耗尽，轮换到下一个
                if self._credential_pool:
                    current = self._credential_pool.current()
                    if current:
                        self._credential_pool.mark_exhausted(
                            current,
                            status_code=429,
                            error_message=str(e)
                        )
                    next_cred = self._credential_pool.select()
                    if next_cred:
                        logger.info(f"Credential exhausted, rotated to: {next_cred.label}")
                raise RuntimeError(f"Rate limited (429): {e}")
            raise RuntimeError(f"API error ({e.status}): {e}")
        except aiohttp.ClientError:
            raise RuntimeError("Network error during model call")
    
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
            messages=messages,  # 传入原始消息，adapter会转换
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
                        "tool_calls": tool_calls
                    }, latency_ms
                    
        except aiohttp.ClientError as e:
            logger.error(f"Anthropic API network error: {e}")
            raise RuntimeError(f"Network error during Anthropic API call: {e}")
    
    async def _execute_tools(self, tool_calls: List[Dict]) -> List[ToolResult]:
        """执行工具调用（带并发限制和单工具超时）"""
        # 检查是否被中断
        if self._interrupt_requested:
            logger.info("Tool execution skipped: interrupt requested")
            return []
        
        results = []
        
        async def execute_with_semaphore(tool_call: Dict) -> ToolResult:
            async with self._tool_semaphore:
                try:
                    return await asyncio.wait_for(
                        self._execute_single_tool(tool_call),
                        timeout=30.0  # 单工具30秒超时
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Tool execution timed out: {tool_call.get('name', 'unknown')}")
                    return ToolResult(
                        tool_call_id=tool_call.get("id", "unknown"),
                        content="Error: tool execution timed out",
                        is_error=True
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Tool execution parameter error: {tool_call.get('name', 'unknown')}: {e}")
                    return ToolResult(
                        tool_call_id=tool_call.get("id", "unknown"),
                        content=f"Error: {type(e).__name__} - {e}",
                        is_error=True
                    )
                except Exception as e:
                    logger.error(f"Tool execution error: {tool_call.get('name', 'unknown')}: {e}")
                    return ToolResult(
                        tool_call_id=tool_call.get("id", "unknown"),
                        content=f"Error: {type(e).__name__} - {e}",
                        is_error=True
                    )
        
        # 并发执行所有工具（受 semaphore 限制）
        tasks = [execute_with_semaphore(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                err_name = type(result).__name__
                err_msg = str(result)
                # 记录详细日志但不暴露给LLM
                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(f"Tool execution timed out: {tool_calls[i].get('name', 'unknown')}")
                    content = "Error: tool execution timed out"
                else:
                    logger.warning(f"Tool execution exception ({err_name}): {tool_calls[i].get('name', 'unknown')}")
                    content = "Error: tool execution failed"
                processed_results.append(ToolResult(
                    tool_call_id=tool_calls[i].get("id", "unknown"),
                    content=content,
                    is_error=True
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_single_tool(self, tool_call: Dict) -> ToolResult:
        """执行单个工具调用"""
        # 获取tool_call的id
        tool_call_id = tool_call.get("id", "unknown")
        
        # 处理OpenAI格式：{type: 'function', function: {name, arguments}}
        if tool_call.get("type") == "function" and "function" in tool_call:
            func_name = tool_call["function"].get("name", "")
            raw_args = tool_call["function"].get("arguments", {})
        else:
            # 兼容旧格式
            func_name = tool_call.get("name", "")
            raw_args = tool_call.get("arguments", {})
        
        # Plugin hook: pre_tool_call
        # 在工具调用前执行，允许插件修改或阻止
        try:
            pre_results = self._invoke_hook(
                "pre_tool_call",
                tool_name=func_name,
                arguments=arguments,
            )
            # 如果有hook返回block指令，跳过工具执行
            for result in pre_results:
                if isinstance(result, dict) and result.get("block"):
                    logger.info(f"Tool {func_name} blocked by hook")
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        content=f"Tool execution blocked by plugin hook",
                        is_error=False
                    )
        except Exception as e:
            logger.warning(f"pre_tool_call hook failed: {e}")
        
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
            return ToolResult(
                tool_call_id="unknown",
                content="Error: tool_call missing 'id' field",
                is_error=True
            )
        if not func_name:
            logger.warning(f"SKIP tool_call: missing 'name' field: {tool_call}")
            return ToolResult(
                tool_call_id=tool_call_id,
                content="Error: tool_call missing 'name' field",
                is_error=True
            )
        
        try:
            # 防御性处理 arguments 类型
            arguments = raw_args if isinstance(raw_args, dict) else {}
            if isinstance(raw_args, str):
                # 如果是字符串，尝试解析为 dict
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse arguments as JSON for tool {func_name}")
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        content="Error: invalid JSON in tool arguments",
                        is_error=True
                    )
            if not isinstance(arguments, dict):
                logger.warning(f"Arguments is not a dict for tool {func_name}: {type(arguments)}")
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content="Error: arguments must be a dict",
                    is_error=True
                )
            
            result = await self.tool_registry.execute(
                name=func_name,
                arguments=arguments
            )
            
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
            
            return ToolResult(
                tool_call_id=tool_call_id,
                content=str(result),
                is_error=False
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_call['name']}, error: {e}")
            
            # 触发tool_complete_callback（错误情况）
            if self.tool_complete_callback:
                try:
                    self.tool_complete_callback(func_name, f"Error: {e}")
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
        执行Skill（自进化核心）
        
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
        进化Skill（基于执行结果学习）
        
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
        
        # 敏感信息过滤正则（覆盖多种凭证格式）
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
        
        # 保存到文件（使用绝对路径）
        import os
        trajectory_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trajectory")
        os.makedirs(trajectory_dir, exist_ok=True)
        trajectory_file = os.path.join(trajectory_dir, f"trajectory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        try:
            with open(trajectory_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # 设置文件权限为600（仅所有者读写）
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
        """
        从SessionDB恢复会话
        
        学习自Hermes会话持久化：
        - 从Hermes SessionDB恢复消息历史
        - 恢复conversation_history
        
        Args:
            session_id: 要恢复的session ID（可选）
            
        Returns:
            是否成功恢复
        """
        if SessionDB is None:
            return False
        
        try:
            db = SessionDB()
            
            # 如果没有指定session_id，尝试获取最近的
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
    # Plugin Hook系统（学习自Hermes）
    # ========================================================================
    
    # 支持的Hook类型
    VALID_HOOKS = {
        "pre_llm_call",      # LLM调用前
        "post_llm_call",     # LLM调用后
        "pre_tool_call",      # 工具调用前
        "post_tool_call",     # 工具调用后
        "on_session_start",    # 会话开始
        "on_session_end",     # 会话结束
    }
    
    def _invoke_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """
        调用指定名称的所有Hook
        
        学习自Hermes invoke_hook：
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
            hook_name: Hook名称（如"pre_llm_call"）
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
        
        学习自Hermes fallback机制：
        - 当主模型API失败时，尝试使用fallback模型
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
        恢复主运行时（Fallback后）
        
        学习自Hermes：
        - 在新的对话轮次开始时，如果上次使用了fallback，尝试恢复主模型
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


# ========================================================================
# Skill工具函数（供Agent调用）
# ========================================================================

def skill_view_func(name: str, file_path: str = None) -> str:
    """
    加载skill完整内容
    
    Args:
        name: skill名称
        file_path: 可选，加载skill下的具体文件
        
    Returns:
        skill内容
    """
    from skills.skills_loader import skill_view as _skill_view, SkillLoadError
    try:
        result = _skill_view(name, file_path)
        if file_path:
            return f"文件: {file_path}\n\n{result['content']}"
        return result['content']
    except SkillLoadError as e:
        return f"Error: {e}"


def skills_list_func(category: str = None) -> str:
    """
    列出所有可用的skill
    
    Args:
        category: 可选，按分类过滤
        
    Returns:
        skill列表
    """
    from skills.skills_loader import skills_list as _skills_list
    skills = _skills_list(category)
    if not skills:
        return "No skills found."
    
    lines = [f"Found {len(skills)} skills:\n"]
    for s in skills:
        lines.append(f"- {s['name']}: {s.get('description', 'No description')[:60]}")
    return "\n".join(lines)


# Skill工具schema
SKILL_TOOL_SCHEMAS = {
    "skill_view": {
        "name": "skill_view",
        "description": "Load the full content of a skill by name. Use this to get the complete instructions for a skill.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the skill to view"
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional: Load a specific file within the skill (e.g., 'references/api.md')"
                }
            },
            "required": ["name"]
        }
    },
    "skills_list": {
        "name": "skills_list",
        "description": "List all available skills. Returns skill names and descriptions.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional: Filter by category (e.g., 'github', 'data-science')"
                }
            }
        }
    }
}


# ========================================================================
# Skill管理工具函数（Hermes 1:1）
# ========================================================================

def skill_manage_func(
    action: str,
    name: str,
    content: str = None,
    category: str = None,
    file_path: str = None,
    file_content: str = None,
    old_string: str = None,
    new_string: str = None,
    replace_all: bool = False,
) -> str:
    """
    管理skill（创建、编辑、删除）
    
    Actions:
    - create: 创建新skill
    - edit: 编辑skill（完整重写）
    - patch: 打补丁（局部修改）
    - delete: 删除skill
    - write_file: 写入skill下的文件
    - remove_file: 删除skill下的文件
    """
    from skills.skills_loader import skill_manage as _skill_manage
    return _skill_manage(
        action=action,
        name=name,
        content=content,
        category=category,
        file_path=file_path,
        file_content=file_content,
        old_string=old_string,
        new_string=new_string,
        replace_all=replace_all,
    )


# Skill管理工具schema
SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "description": (
        "Manage skills (create, update, delete). Skills are your procedural memory — "
        "reusable approaches for recurring task types.\n\n"
        "Actions: create (full SKILL.md + optional category), "
        "patch (old_string/new_string — preferred for fixes), "
        "edit (full SKILL.md rewrite), "
        "delete, write_file, remove_file.\n\n"
        "Create when: complex task succeeded (5+ calls), errors overcome, "
        "user-corrected approach worked, non-trivial workflow discovered.\n"
        "Update when: instructions stale/wrong, missing steps or pitfalls found.\n"
        "After difficult tasks, offer to save as a skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "patch", "edit", "delete", "write_file", "remove_file"],
                "description": "The action to perform"
            },
            "name": {"type": "string", "description": "Skill name"},
            "content": {"type": "string", "description": "Full SKILL.md content for create/edit"},
            "category": {"type": "string", "description": "Category for new skill"},
            "file_path": {"type": "string", "description": "File path within skill"},
            "file_content": {"type": "string", "description": "File content for write_file"},
            "old_string": {"type": "string", "description": "Text to find for patch"},
            "new_string": {"type": "string", "description": "Replacement text for patch"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences"},
        },
        "required": ["action", "name"]
    }
}
