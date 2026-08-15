"""MimirAether AIAgent — wraps MimirAetherAgent for gateway compatibility."""

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# Loki-C 2026-08-15（Mimir 条件1）：宽 except 白名单——AgentLoopExit 是正常退出信号，
# 不能被下面 run_conversation 的 `except Exception` 吞成 "⚠️ Agent error"。
try:
    from agent.agent_loop import AgentLoopExit
except Exception:  # import 失败不影响启动（AgentLoopExit 只在异常路径用）
    AgentLoopExit = None  # type: ignore

# Keep gateway inactivity watchdog alive during long LLM/tool stretches (STAB-01).
_ACTIVITY_HEARTBEAT_INTERVAL = 30.0


class AIAgent:
    """AIAgent wrapper for MimirAetherAgent, compatible with gateway interface.

    Delegates all agent functionality to the real MimirAetherAgent
    in agent.core_loop.
    """

    def __init__(
        self,
        platform: str = "acp",
        enabled_toolsets: Optional[List[str]] = None,
        disabled_toolsets: Optional[List[str]] = None,
        quiet_mode: bool = True,
        session_id: str = "",
        model: str = "",
        provider: Optional[str] = None,
        api_mode: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
        skip_memory: bool = False,
        **kwargs: Any,
    ) -> None:
        self.platform = platform
        self.enabled_toolsets = enabled_toolsets or []
        self.disabled_toolsets = disabled_toolsets or []
        self.quiet_mode = quiet_mode
        self.session_id = session_id
        self.model = model or "deepseek/deepseek-v4-pro"
        self.provider = provider
        self.api_mode = api_mode
        self.base_url = base_url
        self.api_key = api_key
        self.command = command
        self.args = args or []
        self._max_iterations = max_iterations or 90
        self.skip_memory = skip_memory
        self._extra_kwargs = kwargs

        # Callback hooks (set by gateway)
        self.tool_progress_callback: Optional[Any] = None
        self.thinking_callback: Optional[Any] = None
        self.step_callback: Optional[Any] = None
        self.message_callback: Optional[Any] = None

        # Tool surface
        self.tools: Optional[List[Dict[str, Any]]] = None
        self.valid_tool_names: Optional[set] = None

        # Print function
        self._print_fn: Any = lambda *a, **kw: None

        # Interrupt support
        self._interrupt_event: Optional[threading.Event] = None

        # Activity tracker (gateway inactivity timeout + long-running notifications)
        self._last_activity_ts = time.monotonic()
        self._last_activity_desc = "initialized"
        self._current_tool: Optional[str] = None
        self._api_call_count = 0
        
        # Internal real agent (lazy init)
        self._real_agent: Any = None

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    def _touch_activity(
        self,
        desc: str = "",
        *,
        tool: Optional[str] = None,
        increment_api: bool = False,
    ) -> None:
        self._last_activity_ts = time.monotonic()
        if desc:
            self._last_activity_desc = desc
        if tool is not None:
            self._current_tool = tool
        if increment_api:
            self._api_call_count += 1

    def get_activity_summary(self) -> Dict[str, Any]:
        return {
            "seconds_since_activity": time.monotonic() - self._last_activity_ts,
            "last_activity_desc": self._last_activity_desc,
            "current_tool": self._current_tool,
            "api_call_count": self._api_call_count,
            "max_iterations": self._max_iterations,
        }

    def _wrap_step_callback(self, cb: Optional[Callable[..., Any]]) -> Optional[Callable[..., Any]]:
        if cb is None:
            return None

        def _wrapped(iteration: int, prev_tools: list) -> None:
            self._touch_activity(f"iteration {iteration}", increment_api=True)
            if prev_tools:
                last = prev_tools[-1]
                name = last.get("name") if isinstance(last, dict) else str(last)
                if name:
                    self._touch_activity(f"after tool {name}", tool=None)
            cb(iteration, prev_tools)

        return _wrapped

    def _wrap_tool_progress_callback(
        self, cb: Optional[Callable[..., Any]]
    ) -> Optional[Callable[..., Any]]:
        if cb is None:
            return None

        def _wrapped(tool_name: str, *args: Any, **kwargs: Any) -> Any:
            self._touch_activity(f"tool {tool_name}", tool=tool_name)
            return cb(tool_name, *args, **kwargs)

        return _wrapped

    def _sync_callbacks_to_real_agent(self) -> None:
        if self._real_agent is None:
            return
        self._real_agent.step_callback = self._wrap_step_callback(self.step_callback)
        self._real_agent.tool_progress_callback = self._wrap_tool_progress_callback(
            self.tool_progress_callback
        )

    @property
    def context_compressor(self) -> Any:
        """Gateway / `/compress` compatibility: same object as ``MimirAetherAgent.compressor``."""
        return self._get_real_agent().compressor

    async def _compress_context(
        self,
        messages: List[Dict[str, Any]],
        cached_system_prompt: str = "",
        approx_tokens: Optional[int] = None,
        focus_topic: Optional[str] = None,
        task_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[List[Dict[str, Any]], Any]:
        """
        Manual / hygiene compression entry (Gateway, ACP). Delegates to
        ``MimirContextCompressor.compress``; does not split SQLite sessions.
        """
        _ = cached_system_prompt, task_id, kwargs
        comp = self._get_real_agent().compressor
        return await comp.compress(
            messages,
            current_tokens=approx_tokens,
            focus_topic=focus_topic,
        )

    def _get_real_agent(self) -> Any:
        """Lazy-initialize the real MimirAetherAgent."""
        if self._real_agent is None:
            from agent.core_loop import MimirAetherAgent
            
            self._real_agent = MimirAetherAgent(
                model=self.model,
                max_iterations=self._max_iterations,
                platform=self.platform,
                stream_callback=None,
                step_callback=self._wrap_step_callback(self.step_callback),
                tool_progress_callback=self._wrap_tool_progress_callback(
                    self.tool_progress_callback
                ),
                thinking_callback=self.thinking_callback,
                enabled_toolsets=self.enabled_toolsets or None,
                disabled_toolsets=self.disabled_toolsets or None,
            )
        else:
            self._sync_callbacks_to_real_agent()
        return self._real_agent

    def interrupt(self, message: str = "") -> None:
        """Request the agent to interrupt current execution."""
        if self._real_agent is not None and hasattr(self._real_agent, "interrupt"):
            self._real_agent.interrupt(message)
        if self._interrupt_event:
            self._interrupt_event.set()

    def _invalidate_system_prompt(self) -> None:
        """Invalidate cached system prompt (called after tool surface changes)."""
        pass

    def run_conversation(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]] = None,
        task_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run a conversation turn through the real MimirAetherAgent.
        
        Adapts between gateway interface (dict return) and MimirAetherAgent
        interface (async, str return).
        """
        try:
            self._touch_activity("run_conversation start")
            self._sync_callbacks_to_real_agent()
            agent = self._get_real_agent()

            stop_heartbeat = threading.Event()

            def _activity_heartbeat() -> None:
                while not stop_heartbeat.wait(_ACTIVITY_HEARTBEAT_INTERVAL):
                    self._touch_activity("agent turn in progress")

            heartbeat = threading.Thread(target=_activity_heartbeat, daemon=True)
            heartbeat.start()
            from agent.async_bridge import run_async
            from agent.auxiliary_client import cleanup_stale_async_clients
            
            try:
                # MimirAetherAgent.run_conversation is async, returns str
                # C1: 传递前置对话历史以保持飞书多轮连续性
                # STAB-02: run_async (persistent loop) — not asyncio.run() per turn
                response = run_async(agent.run_conversation(
                    user_message,
                    conversation_history=conversation_history,
                ))
            finally:
                stop_heartbeat.set()
                heartbeat.join(timeout=1.0)
                self._current_tool = None
                self._touch_activity("run_conversation end")
                cleanup_stale_async_clients()
            
            return {
                "final_response": response,
                "messages": conversation_history or [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        except Exception as exc:
            if AgentLoopExit is not None and isinstance(exc, AgentLoopExit):
                # Loki-C（Mimir 条件1）：AgentLoopExit 是统一出口信号，不吞——继续冒泡
                raise
            self._current_tool = None
            self._touch_activity("run_conversation error")
            return {
                "final_response": f"⚠️ Agent error: {exc}",
                "messages": conversation_history or [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }


def main() -> None:
    """CLI entry point."""
    print("MimirAether AIAgent — wraps MimirAetherAgent for gateway compatibility")
