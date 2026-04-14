"""
MimirAether Agent Core Loop

学习自Hermes AIAgent架构，重新实现的核心Agent类。

核心功能：
- 主对话循环
- 工具调用处理
- 上下文管理
- 迭代预算控制
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Union
from enum import Enum

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
    ):
        """
        初始化MimirAether Agent
        
        Args:
            model: 使用的模型
            max_iterations: 最大迭代次数
            platform: 运行平台
            system_prompt: 系统提示
            save_trajectories: 是否保存轨迹
        """
        self.model = model
        self.max_iterations = max_iterations
        self.platform = platform
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.save_trajectories = save_trajectories
        
        # 初始化组件
        self.budget = IterationBudget(max_iterations)
        self.tool_registry = ToolRegistry()
        self.conversation_history: List[Message] = []
        self.max_history_length = 100  # 对话历史最大长度，防止内存耗尽
        
        # 轨迹记录
        self._trajectory: List[Dict] = []
        
        # 工具调用并发限制（最多同时执行5个工具）
        self._tool_semaphore = asyncio.Semaphore(5)
        
        # 注册内置工具
        self._register_builtin_tools()
        
        logger.info(f"MimirAether initialized with model: {model}")
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        try:
            # 使用try/except处理相对导入和绝对导入两种情况
            try:
                from ..tools.builtin import get_tool_functions, get_all_tools
            except ImportError:
                # 当作为顶层包导入时，使用绝对导入
                import sys
                from pathlib import Path
                
                # 将MimirAether根目录添加到path
                mimir_root = Path(__file__).parent.parent
                if str(mimir_root) not in sys.path:
                    sys.path.insert(0, str(mimir_root))
                
                from tools.builtin import get_tool_functions, get_all_tools
            
            functions = get_tool_functions()
            schemas = get_all_tools()
            
            for name, func in functions.items():
                schema = schemas.get(name, {})
                self.tool_registry.register(name, func, schema)
            
            logger.info(f"Registered {len(functions)} builtin tools")
        except ImportError as e:
            logger.warning(f"Failed to import builtin tools: {e}")
    
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
        # 开始轨迹记录
        if self.save_trajectories:
            self._start_trajectory()
        
        # 添加用户消息到历史
        self.conversation_history.append(Message(
            role=MessageRole.USER,
            content=user_message
        ))
        
        # 限制历史长度，防止内存耗尽
        if len(self.conversation_history) > self.max_history_length:
            # 保留系统消息和最新的对话
            system_msgs = [m for m in self.conversation_history if m.role == MessageRole.SYSTEM]
            other_msgs = [m for m in self.conversation_history if m.role != MessageRole.SYSTEM]
            self.conversation_history = system_msgs + other_msgs[-self.max_history_length:]
        
        try:
            # 主循环
            while True:
                # 检查预算
                if not await self.budget.consume():
                    logger.warning("Iteration budget exhausted")
                    return "抱歉，任务迭代次数已达上限。"
                
                # 每次迭代都重建消息列表（使用当前全部历史）
                messages = self._build_full_messages()
                
                # 调用模型（带超时控制）
                try:
                    response = await asyncio.wait_for(
                        self._call_model(messages),
                        timeout=120.0  # 120秒超时
                    )
                except asyncio.TimeoutError:
                    logger.error("Model call timed out")
                    return "抱歉，模型响应超时，请重试。"
                except Exception as e:
                    logger.error(f"Model call failed: {e}")
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
                
                # 检查是否有工具调用
                if response.get("tool_calls") and response_content:
                    # 同时有文本和工具调用：先执行工具，再返回文本
                    tool_results = await self._execute_tools(response["tool_calls"])
                    
                    # 添加工具结果到历史
                    for result in tool_results:
                        self.conversation_history.append(Message(
                            role=MessageRole.TOOL,
                            content=result.content,
                            tool_call_id=result.tool_call_id
                        ))
                    
                    # 工具调用后 refund（只refund一次，无论多少工具）
                    await self.budget.refund()
                    
                    # 返回文本响应
                    return response_content
                
                if response.get("tool_calls"):
                    # 只有工具调用，没有文本：执行工具
                    tool_results = await self._execute_tools(response["tool_calls"])
                    
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
    
    async def _call_model(self, messages: List[Dict]) -> Dict:
        """
        调用模型API
        
        支持 MiniMax API，需设置环境变量 MINIMAX_API_KEY
        或在初始化时传入 model_provider_config
        """
        import os
        import aiohttp
        
        # 获取API配置
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")
        model_name = os.environ.get("MINIMAX_MODEL", "MiniMax-M2")
        
        if not api_key:
            raise ValueError("MINIMAX_API_KEY environment variable not set")
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建请求体（OpenAI兼容格式）
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        # 发送请求
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        # 不泄露原始响应内容
                        logger.warning("API call failed")
                        raise RuntimeError("Model API request failed")
                    
                    result = await response.json()
                    
                    # 安全提取助手响应（边界检查）
                    choices = result.get("choices")
                    if not choices or len(choices) == 0:
                        raise RuntimeError("Invalid API response: no choices")
                    
                    assistant_message = choices[0].get("message")
                    if not assistant_message:
                        raise RuntimeError("Invalid API response: no message in choice")
                    
                    return {
                        "content": assistant_message.get("content") or "",
                        "tool_calls": assistant_message.get("tool_calls")
                    }
        except aiohttp.ClientError:
            raise RuntimeError("Network error during model call")
    
    async def _execute_tools(self, tool_calls: List[Dict]) -> List[ToolResult]:
        """执行工具调用（带并发限制和单工具超时）"""
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
        # 校验tool_call必需字段
        if "id" not in tool_call:
            logger.warning(f"SKIP tool_call: missing 'id' field: {tool_call}")
            return ToolResult(
                tool_call_id="unknown",
                content="Error: tool_call missing 'id' field",
                is_error=True
            )
        if "name" not in tool_call:
            logger.warning(f"SKIP tool_call: missing 'name' field: {tool_call}")
            return ToolResult(
                tool_call_id=tool_call.get("id", "unknown"),
                content="Error: tool_call missing 'name' field",
                is_error=True
            )
        
        try:
            # 防御性处理 arguments 类型
            arguments = tool_call.get("arguments", {})
            if isinstance(arguments, str):
                # 如果是字符串，尝试解析为 dict
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse arguments as JSON for tool {tool_call.get('name', 'unknown')}")
                    return ToolResult(
                        tool_call_id=tool_call["id"],
                        content="Error: invalid JSON in tool arguments",
                        is_error=True
                    )
            if not isinstance(arguments, dict):
                logger.warning(f"Arguments is not a dict for tool {tool_call.get('name', 'unknown')}: {type(arguments)}")
                return ToolResult(
                    tool_call_id=tool_call["id"],
                    content="Error: arguments must be a dict",
                    is_error=True
                )
            
            result = await self.tool_registry.execute(
                name=tool_call["name"],
                arguments=arguments
            )
            return ToolResult(
                tool_call_id=tool_call["id"],
                content=str(result),
                is_error=False
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_call['name']}, error: {e}")
            return ToolResult(
                tool_call_id=tool_call["id"],
                content="Error: tool execution failed",
                is_error=True
            )

    
    def build_system_prompt(self) -> str:
        """构建系统提示"""
        return self.system_prompt
    
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
        logger.info("Agent reset")


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
