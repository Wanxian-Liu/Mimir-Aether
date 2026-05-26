"""
MimirAgentLoop - Pure Agent Execution Engine

Extracted from MimirAetherAgent.run_conversation() following the Hermes
microkernel pattern. This class is a pure execution engine:

  - Receives: model caller, tool schemas, tool dispatcher, messages
  - Runs: the tool-calling loop (standard OpenAI-spec)
  - Returns: AgentResult with full metadata

It does NOT manage models, credentials, system prompts, or tool registration.
Those are MimirAetherAgent's responsibility (the configuration layer).

Key design from Hermes:
  - ThreadPoolExecutor for sync tool calls (async bridge)
  - Persistent event loops via async_bridge.py
  - AgentResult with ToolError for structured error collection
  - Reasoning extraction across provider formats
  - Fallback <tool_call> parser
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable

from .async_bridge import get_tool_executor
from .conversation_nudges import (
    maybe_memory_nudge_message,
    maybe_skill_nudge_message,
)
from .intent_action_guard import (
    MAX_INTENT_NUDGES,
    build_nudge_message,
    guard_enabled,
    should_block_text_only_finish,
)
# 统一类型: 从 types.py 导入 (Phase 3 M1)
from .types import AgentLoopToolError as ToolError, AgentLoopResult as AgentResult

logger = logging.getLogger(__name__)


# ============== Helpers ==============

def _extract_reasoning(message) -> Optional[str]:
    """Extract reasoning from message - handles dict and object forms."""
    if hasattr(message, "reasoning_content") and message.reasoning_content:
        return message.reasoning_content
    if hasattr(message, "reasoning") and message.reasoning:
        return message.reasoning
    if hasattr(message, "reasoning_details") and message.reasoning_details:
        for detail in message.reasoning_details:
            if hasattr(detail, "text") and detail.text:
                return detail.text
            if isinstance(detail, dict) and detail.get("text"):
                return detail["text"]
    return None


def _tc_to_dict(tc) -> dict:
    """Normalize tool_call to canonical dict (handles object and dict forms)."""
    if isinstance(tc, dict):
        func = tc.get("function", {})
        return {
            "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
            "type": "function",
            "function": {
                "name": func.get("name", tc.get("name", "")),
                "arguments": func.get("arguments", tc.get("arguments", "{}")),
            },
        }
    return {
        "id": tc.id,
        "type": "function",
        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
    }


def _get_tc_name(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("function", {}).get("name", tc.get("name", ""))
    return tc.function.name


def _get_tc_args(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("function", {}).get("arguments", tc.get("arguments", "{}"))
    return tc.function.arguments


def _get_tc_id(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("id", "")
    return tc.id


# ============== The Loop ==============

class MimirAgentLoop:
    """Pure agent execution engine following the Hermes microkernel pattern.

    Responsibilities:
      - Call the model repeatedly until it stops calling tools
      - Dispatch tool calls to a provided executor
      - Collect errors and metadata in AgentResult
      - Apply budget controls
      - Support interruption

    Does NOT manage: models, credentials, system prompts, tool registration.
    Those belong to the configuration layer (MimirAetherAgent).
    """

    def __init__(
        self,
        model_call: Callable[[List[Dict[str, Any]]], Awaitable[Any]],
        tool_schemas: List[Dict[str, Any]],
        valid_tool_names: Set[str],
        tool_dispatcher: Callable[[str, dict, Optional[str]], str],
        max_turns: int = 90,
        task_id: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        budget_config: Any = None,
        interrupt_check: Optional[Callable[[], bool]] = None,
    ):
        self.model_call = model_call
        self.tool_schemas = tool_schemas
        self.valid_tool_names = valid_tool_names
        self.tool_dispatcher = tool_dispatcher
        self.max_turns = max_turns
        self.task_id = task_id or str(uuid.uuid4())
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = extra_body
        self.budget_config = budget_config
        self.interrupt_check = interrupt_check or (lambda: False)
        # Optional execution pipeline (recording + quality tracking)
        self._recorder = None

    async def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        """Execute the full agent loop.

        Args:
            messages: Initial conversation messages (system + user).
                      Modified IN-PLACE.

        Returns:
            AgentResult with full history and metadata.
        """
        reasoning_per_turn: List[Optional[str]] = []
        tool_errors: List[ToolError] = []

        user_task = None
        for msg in messages:
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, str) and c.strip():
                    user_task = c.strip()[:500]
                break

        import time as _time
        _executor = get_tool_executor()

        try:
            from agent.execution_pipeline import start_execution_pipeline
            start_execution_pipeline(task_name=user_task or self.task_id, session_id=self.task_id)
        except Exception:
            pass

        intent_nudges = 0
        tool_calls_so_far = 0

        for turn in range(self.max_turns):
            if self.interrupt_check():
                logger.info("Loop interrupted at turn %d", turn + 1)
                self._close_pipeline(user_task)
                return AgentResult(
                    messages=messages, turns_used=turn + 1,
                    finished_naturally=False, reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors, interrupted=True,
                )

            turn_start = _time.monotonic()

            mem_nudge = maybe_memory_nudge_message(turn)
            if mem_nudge:
                messages.append({"role": "user", "content": mem_nudge})
            skill_nudge = maybe_skill_nudge_message(turn, tool_calls_so_far)
            if skill_nudge:
                messages.append({"role": "user", "content": skill_nudge})

            # --- Call model ---
            api_start = _time.monotonic()
            try:
                response = await self.model_call(messages)
            except Exception as e:
                api_elapsed = _time.monotonic() - api_start
                logger.error("API call failed on turn %d (%.1fs): %s", turn + 1, api_elapsed, e)
                self._close_pipeline(user_task)
                return AgentResult(
                    messages=messages, turns_used=turn + 1,
                    finished_naturally=False, reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors,
                )
            api_elapsed = _time.monotonic() - api_start

            if not response:
                self._close_pipeline(user_task)
                return AgentResult(
                    messages=messages, turns_used=turn + 1,
                    finished_naturally=False, reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors,
                )

            # --- Extract response parts (dict, MimirAether-flat, or object) ---
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    # Standard OpenAI format: {"choices": [{"message": {...}}]}
                    msg = choices[0].get("message", {})
                    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                    _tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
                    _reasoning = msg.get("reasoning_content") if isinstance(msg, dict) else _extract_reasoning(msg)
                elif "content" in response or "tool_calls" in response:
                    # MimirAether flat format: {"content": ..., "tool_calls": ...}
                    content = response.get("content", "") or ""
                    _tool_calls = response.get("tool_calls")
                    _reasoning = response.get("reasoning_content")
                else:
                    self._close_pipeline(user_task)
                    return AgentResult(
                        messages=messages, turns_used=turn + 1,
                        finished_naturally=False, reasoning_per_turn=reasoning_per_turn,
                        tool_errors=tool_errors,
                    )
            else:
                if not getattr(response, "choices", None):
                    self._close_pipeline(user_task)
                    return AgentResult(
                        messages=messages, turns_used=turn + 1,
                        finished_naturally=False, reasoning_per_turn=reasoning_per_turn,
                        tool_errors=tool_errors,
                    )
                msg = response.choices[0].message
                content = getattr(msg, "content", "") or ""
                _tool_calls = getattr(msg, "tool_calls", None)
                _reasoning = _extract_reasoning(msg)

            reasoning_per_turn.append(_reasoning)

            # --- Fallback parser ---
            if not _tool_calls and content and self.tool_schemas and "<tool_call>" in (content or ""):
                _tool_calls = _fallback_parse_tool_calls(content)
                if _tool_calls:
                    tag_idx = content.find("<tool_call>")
                    content = content[:tag_idx].strip()

            # --- Tool calls? ---
            if _tool_calls:
                normalized = [_tc_to_dict(tc) for tc in _tool_calls]
                tool_calls_so_far += len(normalized)
                msg_dict: Dict[str, Any] = {
                    "role": "assistant", "content": content or "",
                    "tool_calls": normalized,
                }
                if _reasoning:
                    msg_dict["reasoning_content"] = _reasoning
                messages.append(msg_dict)

                # Use normalized calls for dispatch so missing `id` matches assistant.tool_calls
                # (dict path in _tc_to_dict synthesizes call_<uuid> when id absent).
                for tc in normalized:
                    tname = _get_tc_name(tc)
                    targs_raw = _get_tc_args(tc)
                    tid = _get_tc_id(tc)

                    if tname not in self.valid_tool_names:
                        tr = json.dumps({"error": f"Unknown tool '{tname}'."})
                        tool_errors.append(ToolError(
                            turn=turn + 1, tool_name=tname,
                            arguments=str(targs_raw)[:200],
                            error=f"Unknown tool '{tname}'", tool_result=tr,
                        ))
                        messages.append({"role": "tool", "tool_call_id": tid, "content": tr})
                        continue

                    try:
                        args = json.loads(targs_raw) if isinstance(targs_raw, str) else (targs_raw or {})
                    except json.JSONDecodeError as e:
                        tr = json.dumps({"error": f"Invalid JSON: {e}"})
                        tool_errors.append(ToolError(
                            turn=turn + 1, tool_name=tname,
                            arguments=str(targs_raw)[:200],
                            error=f"Invalid JSON: {e}", tool_result=tr,
                        ))
                        messages.append({"role": "tool", "tool_call_id": tid, "content": tr})
                        continue

                    try:
                        t0 = _time.monotonic()
                        loop = asyncio.get_event_loop()
                        _tn, _ta, _tid = tname, args, self.task_id
                        tool_result = await loop.run_in_executor(
                            _executor,
                            lambda tn=_tn, ta=_ta, tid=_tid: self.tool_dispatcher(tn, ta, tid),
                        )
                        telapsed = _time.monotonic() - t0

                        pool_q = _executor._work_queue.qsize()
                        if telapsed > 30:
                            logger.warning(
                                "[%s] turn %d: %s took %.1fs (pool q=%d)",
                                self.task_id[:8], turn + 1, tname, telapsed, pool_q,
                            )
                        self._record_tool(tname, args, success=True,
                                          duration_ms=telapsed * 1000,
                                          result_summary=str(tool_result)[:200])
                    except Exception as e:
                        telapsed = _time.monotonic() - t0
                        tool_result = json.dumps({
                            "error": f"{type(e).__name__}: {str(e)}"
                        })
                        tool_errors.append(ToolError(
                            turn=turn + 1, tool_name=tname,
                            arguments=str(targs_raw)[:200],
                            error=f"{type(e).__name__}: {str(e)}",
                            tool_result=tool_result,
                        ))
                        self._record_tool(tname, args, success=False,
                                          error_message=str(e)[:500],
                                          duration_ms=telapsed * 1000,
                                          result_summary=str(tool_result)[:200])

                    # Budget control
                    try:
                        from tools.tool_result_storage import maybe_persist_tool_result
                        from tools.terminal_tool import get_active_env
                        tool_result = maybe_persist_tool_result(
                            content=tool_result, tool_name=tname,
                            tool_use_id=tid,
                            env=get_active_env(self.task_id),
                            config=self.budget_config,
                        )
                    except Exception:
                        pass

                    messages.append({"role": "tool", "tool_call_id": tid, "content": tool_result})

                turn_elapsed = _time.monotonic() - turn_start
                logger.info(
                    "[%s] turn %d: api=%.1fs, %d tools, total=%.1fs",
                    self.task_id[:8], turn + 1, api_elapsed,
                    len(_tool_calls), turn_elapsed,
                )
            else:
                # No tool calls — finish unless intent-action guard blocks deferral.
                msg_dict = {"role": "assistant", "content": content or ""}
                if _reasoning:
                    msg_dict["reasoning_content"] = _reasoning
                messages.append(msg_dict)

                block_finish = (
                    guard_enabled()
                    and intent_nudges < MAX_INTENT_NUDGES
                    and should_block_text_only_finish(
                        messages,
                        content or "",
                        has_tool_schemas=bool(self.tool_schemas),
                    )
                )
                if block_finish:
                    intent_nudges += 1
                    messages.append({"role": "user", "content": build_nudge_message()})
                    logger.warning(
                        "[%s] turn %d: intent-action guard nudge %d/%d (deferred text-only)",
                        self.task_id[:8], turn + 1, intent_nudges, MAX_INTENT_NUDGES,
                    )
                    continue

                logger.info(
                    "[%s] turn %d: api=%.1fs, no tools (finished)",
                    self.task_id[:8], turn + 1, api_elapsed,
                )
                self._close_pipeline(user_task)
                return AgentResult(
                    messages=messages, turns_used=turn + 1,
                    finished_naturally=True, reasoning_per_turn=reasoning_per_turn,
                    tool_errors=tool_errors,
                )

        # Hit max turns
        logger.info("Agent hit max_turns (%d)", self.max_turns)
        self._close_pipeline(user_task)
        return AgentResult(
            messages=messages, turns_used=self.max_turns,
            finished_naturally=False, reasoning_per_turn=reasoning_per_turn,
            tool_errors=tool_errors,
        )

    def _close_pipeline(self, task_name: str = "") -> None:
        """Defensive close of execution pipeline (best-effort, never raises)."""
        try:
            from agent.execution_pipeline import (
                close_execution_pipeline,
                schedule_post_close_evolution,
            )
            from agent.jepa_session_hook import schedule_post_close_jepa_cycle
            from agent.post_close_analysis import schedule_post_close_analysis

            task = task_name or self.task_id
            result = close_execution_pipeline(
                task_name=task,
                session_id=self.task_id,
            )
            schedule_post_close_analysis(
                result,
                task_name=task,
                session_id=self.task_id,
            )
            schedule_post_close_evolution(result)
            schedule_post_close_jepa_cycle(result, session_id=self.task_id)
        except Exception:
            pass

    def _record_tool(
        self,
        tool_name: str,
        arguments: dict,
        *,
        success: bool,
        error_message: str = "",
        duration_ms: float = 0.0,
        result_summary: str = "",
    ) -> None:
        """Record tool execution to the active pipeline (if any).

        No-op when execution recording is not active.  Always succeeds —
        a recording failure must never break the agent loop.
        """
        try:
            from agent.execution_pipeline import record_tool_call
            record_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
                result_summary=result_summary,
                session_id=self.task_id,
            )
        except Exception:
            pass  # Recording is best-effort


def _fallback_parse_tool_calls(content: str) -> Optional[List[dict]]:
    """Parse <tool_call> tags from content when structured tool_calls absent."""
    import re as _re
    pattern = _re.compile(
        r"<tool_call>\s*(.*?)\s*</tool_call>|<tool_call>\s*(.*)",
        _re.DOTALL,
    )
    matches = pattern.findall(content)
    if not matches:
        return None
    parsed = []
    for m in matches:
        raw = m[0] or m[1]
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
            if "name" in data:
                parsed.append({
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": data["name"],
                        "arguments": json.dumps(
                            data.get("arguments", {}), ensure_ascii=False
                        ),
                    },
                })
        except Exception:
            pass
    return parsed or None


STRING_PARAM = {"type": "string"}


def tool_schema(name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible helper to build OpenAI function tool schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


class MimirAetherAgentLoop:
    """Compatibility facade for legacy tests/code expecting old constructor."""

    def __init__(
        self,
        chat_fn: Callable[[List[Dict[str, Any]]], Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_turns: int = 90,
        task_id: Optional[str] = None,
    ):
        self._chat_fn = chat_fn
        self._handlers: Dict[str, Callable[[str, dict, Optional[str]], Any]] = {}
        self._tool_schemas = tools or []
        valid_names = {
            t.get("function", {}).get("name")
            for t in self._tool_schemas
            if isinstance(t, dict)
        }
        valid_names = {n for n in valid_names if n}

        async def _model_call(messages: List[Dict[str, Any]]) -> Any:
            out = self._chat_fn(messages)
            if asyncio.iscoroutine(out):
                return await out
            return out

        def _dispatch(name: str, args: dict, session_id: Optional[str]) -> str:
            handler = self._handlers.get(name)
            if handler is None:
                raise NotImplementedError(f"Tool handler not implemented: '{name}'")
            result = handler(name, args, session_id)
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

        self._loop = MimirAgentLoop(
            model_call=_model_call,
            tool_schemas=self._tool_schemas,
            valid_tool_names=valid_names,
            tool_dispatcher=_dispatch,
            max_turns=max_turns,
            task_id=task_id,
        )
        self.valid_tool_names = self._loop.valid_tool_names

    def register_tool(self, name: str, handler: Callable[[str, dict, Optional[str]], Any]) -> None:
        self._handlers[name] = handler

    def register_tools(self, handlers: Dict[str, Callable[[str, dict, Optional[str]], Any]]) -> None:
        for name, handler in handlers.items():
            self.register_tool(name, handler)

    async def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        return await self._loop.run(messages)


class SimpleAgentLoop(MimirAetherAgentLoop):
    """Synchronous wrapper around MimirAetherAgentLoop."""

    def __init__(
        self,
        chat_fn: Callable[[List[Dict[str, Any]]], Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_turns: int = 90,
        task_id: Optional[str] = None,
    ):
        super().__init__(chat_fn=chat_fn, tools=tools, max_turns=max_turns, task_id=task_id)

    def tool(self, name: str) -> Callable[[Callable[[dict], Any]], Callable[[dict], Any]]:
        def _decorator(fn: Callable[[dict], Any]) -> Callable[[dict], Any]:
            def _adapter(_tool_name: str, args: dict, _session_id: Optional[str]) -> Any:
                return fn(args)
            self.register_tool(name, _adapter)
            return fn
        return _decorator

    def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        return asyncio.run(super().run(messages))
