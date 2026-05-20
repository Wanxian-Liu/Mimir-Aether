"""
ExecMixin — Tool execution: dedup, repair, execute tools.

Extracted from MimirAetherAgent (agent/core_loop.py) as part of d4 split.
"""

from __future__ import annotations

import asyncio
import functools
import json
import time

from agent.async_bridge import get_tool_executor
from agent.types import ToolError, ToolResult, _get_tool_arguments, _get_tool_id, _get_tool_name
import tools.registry as _tool_registry_module

_tool_executor = get_tool_executor()

from typing import List, Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core_loop import MimirAetherAgent

import logging
logger = logging.getLogger(__name__)

# === Module-level helper classes (extracted from core_loop.py) ===

class ToolRegistry:
    """
    ⚠️ DEPRECATED: 工具注册表兼容层。
    委托到 tools.registry.registry，仅保留用于向后兼容。
    新代码应直接使用 tools.registry.registry。
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




class _BuiltinToolBackend:
    """Default tool path: semaphore + timeouts + registry dispatch (see ``_builtin_execute_tools``)."""

    __slots__ = ("_agent",)

    def __init__(self, agent: "MimirAetherAgent") -> None:
        self._agent = agent

    async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0) -> List[ToolResult]:
        return await self._agent._builtin_execute_tools(tool_calls, turn)




class ExecMixin:
    """Tool execution: dedup, repair, execute tools.

    Designed to be mixed into MimirAetherAgent.
    """
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
        valid_names = set(_tool_registry_module.registry.get_all_tool_names())
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
        # Tool progress: notify user tools are running
        _tool_labels = []
        for tc in tool_calls:
            fn_name = _get_tool_name(tc) or "unknown"
            _tool_labels.append(fn_name)
        _progress_msg = f"🔧 执行工具: {', '.join(_tool_labels[:4])}{'...' if len(_tool_labels) > 4 else ''}"
        if _tool_labels:
            self._fire_stream_delta(_progress_msg + "\n")

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

        # Tool completion summary
        _ok_count = sum(1 for r in processed_results if not r.is_error)
        _err_count = sum(1 for r in processed_results if r.is_error)
        if _err_count > 0:
            self._fire_stream_delta(f"⚠️ {_ok_count}成功 {_err_count}失败\n")
        elif _ok_count > 0:
            self._fire_stream_delta(f"✅ 已完成 ({_ok_count}个工具)\n")

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
            # P0-1: 统一参数修复 → agent/tools/repair.py
            from .tools.repair import repair_tool_arguments
            arguments = repair_tool_arguments(func_name, raw_args)
            
            # write_file 修复失败 → 返回错误
            if func_name == "write_file" and isinstance(arguments, dict) and "path" not in arguments:
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error="write_file needs path and content",
                    tool_result="Error: write_file requires path and content in JSON format",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content="Error: write_file requires path and content in JSON format",
                    is_error=True
                )
            # P0-1: arguments 已在 repair_tool_arguments 中标准化为 dict
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

            # 类型强制：LLM常见类型不匹配 → 强制对齐JSON Schema
            from model_tools import coerce_tool_args
            arguments = coerce_tool_args(func_name, arguments)

            # ── 统一 dispatch：通过 tools.registry.registry.dispatch() ──
            # dispatch() 返回 JSON 字符串，统一处理错误格式。
            # Sync handler 在线程池中运行以避免阻塞 event loop。
            # parent_agent=self 通过 partial 绑定，避免 run_in_executor 不支持 kwargs。
            entry = _tool_registry_module.registry._tools.get(func_name)
            if entry is not None and not entry.is_async:
                _dispatch_bound = functools.partial(
                    _tool_registry_module.registry.dispatch,
                    func_name, arguments,
                    parent_agent=self,
                )
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    _tool_executor,
                    _dispatch_bound,
                )
            else:
                result = _tool_registry_module.registry.dispatch(func_name, arguments, parent_agent=self)

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
            logger.error("Tool execution failed: %s, error: %s", func_name or "unknown", e)
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


