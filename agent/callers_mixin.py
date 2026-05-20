"""
CallersMixin — LLM calling: OpenAI/Anthropic adapters, streaming.

Extracted from MimirAetherAgent (agent/core_loop.py) as part of d4 split.
"""

from __future__ import annotations

import asyncio
import json
import time

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .types import MessageRole

if TYPE_CHECKING:
    from agent.core_loop import MimirAetherAgent

import logging
logger = logging.getLogger(__name__)

# === Module-level helper classes (extracted from core_loop.py) ===

class _BuiltinLlmBackend:
    """Default LLM path: HTTP / Anthropic / OpenAI-compatible (see ``_builtin_call_model_with_tokens``)."""

    __slots__ = ("_agent",)

    def __init__(self, agent: "MimirAetherAgent") -> None:
        self._agent = agent

    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        return await self._agent._builtin_call_model_with_tokens(messages, session_id)




class CallersMixin:
    """LLM calling: OpenAI/Anthropic adapters, streaming.

    Designed to be mixed into MimirAetherAgent.
    """
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
                        _err_detail = error_text[:200] if error_text else "(empty body)"
                        raise RuntimeError(f"Stream API error {response.status}: {_err_detail}")

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
            self.compressor.ingest_usage(
                {
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": int(total),
                }
            )
        except Exception as _e:
            logger.debug("compressor.ingest_usage skipped: %s", _e)

    def _build_full_messages(self) -> List[Dict]:
        """构建完整消息列表(用于API调用)

        注意：跨会话前缀缓存（multi-block system + cache_control）不在此处处理，
        而是在 _builtin_call_model_with_tokens 的 Anthropic 路径中按需注入。
        """
        messages = []

        # 系统提示（单字符串，非多block）
        messages.append({
            "role": "system",
            "content": self.system_prompt,
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
            # P0-4: 传播 C1 注入标记到 dict，compressor 跳过计数
            if getattr(msg, '_c1_injected', False):
                msg_dict["_c1_injected"] = True

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

        # 统一出口防护：修复所有路径可能产生的孤儿 tool 消息
        messages = self._sanitize_tool_messages(messages)

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
        # Extract last user message for smart routing
        _user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                _user_msg = m.get("content", "") or ""
                if isinstance(_user_msg, list):
                    _user_msg = " ".join(p.get("text", "") for p in _user_msg if isinstance(p, dict) and p.get("type") == "text")
                break
        api_config = self._resolve_api_config(model_name, user_message=_user_msg)
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

        # 3. 构建工具schemas（使用 toolset 解析，支持 includes + 启用/禁用）
        from tools.toolsets import resolve_enabled_tools
        tool_names = resolve_enabled_tools(
            self.enabled_toolsets or None,
            disabled=self.disabled_toolsets or None,
        )
        tool_schemas = _tool_registry_module.registry.get_definitions(
            set(tool_names)
        )

        # 4. 分发到具体调用路径
        # 路径A: Anthropic API
        if is_anthropic:
            # 应用跨会话前缀缓存（仅Claude + Anthropic/OpenRouter）
            if self._supports_prefix_cache(model_name, base_url, is_anthropic=True):
                # 重建system为多block结构 → 标记stable prefix 1h
                parts = self._build_system_prompt_parts()
                new_content = []
                if parts.get("stable"):
                    new_content.append({"type": "text", "text": parts["stable"]})
                if parts.get("context"):
                    new_content.append({"type": "text", "text": parts["context"]})
                if parts.get("volatile"):
                    new_content.append({"type": "text", "text": parts["volatile"]})
                if new_content:
                    messages = copy.deepcopy(messages)
                    messages[0]["content"] = new_content
                # 注入 cache_control 断点
                from agent.prompt_caching import apply_prefix_cache
                messages = apply_prefix_cache(
                    messages, long_ttl="1h", rolling_ttl="5m",
                )
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

        # 路径C: 标准非流式调用(OpenAI兼容) → P1-5 提取为独立方法
        return await self._call_openai_compatible_nonstreaming(
            base_url=base_url, api_key=api_key, model_name=model_name,
            messages=messages, tool_schemas=tool_schemas,
            max_tokens=max_tokens, session_id=session_id, start=start,
        )

    async def _call_openai_compatible_nonstreaming(
        self, *, base_url: str, api_key: str, model_name: str,
        messages: List[Dict], tool_schemas: List[Dict],
        max_tokens: int, session_id: str, start: float,
    ) -> tuple[Dict, float]:
        """OpenAI-compatible non-streaming API call (P1-5: 从 _builtin_call_model 提取)."""
        import aiohttp
        
        # 转换model名为API接受的格式
        # 注意: OpenRouter的model格式是"provider/model-name"，而官方API通常只需要"model-name"
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
                    import time
                    latency_ms = (time.monotonic() - start) * 1000

                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning(f"API call failed: {response.status}, response: {error_text[:500]}")
                        _err_detail = error_text[:300] if error_text else "(empty body)"
                        raise RuntimeError(f"Model API request failed: {response.status}: {_err_detail}")

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
                        raise RuntimeError(f"Anthropic API request failed: {response.status}: {error_text[:300]}")

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

