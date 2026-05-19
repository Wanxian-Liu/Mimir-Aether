"""MimirAether AIAgent — wraps MimirAetherAgent for gateway compatibility."""

import threading
from typing import Any, Dict, List, Optional, Tuple


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
        
        # Internal real agent (lazy init)
        self._real_agent: Any = None

    @property
    def context_compressor(self) -> Any:
        """Gateway / `/compress` compatibility: same object as ``MimirAetherAgent.compressor``."""
        return self._get_real_agent().compressor

    def _compress_context(
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
        return comp.compress(
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
                step_callback=self.step_callback,
                tool_progress_callback=self.tool_progress_callback,
                thinking_callback=self.thinking_callback,
                enabled_toolsets=self.enabled_toolsets or None,
                disabled_toolsets=self.disabled_toolsets or None,
            )
        return self._real_agent

    def interrupt(self, message: str = "") -> None:
        """Request the agent to interrupt current execution."""
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
            agent = self._get_real_agent()
            import asyncio
            
            # MimirAetherAgent.run_conversation is async, returns str
            # C1: 传递前置对话历史以保持飞书多轮连续性
            response = asyncio.run(agent.run_conversation(
                user_message,
                conversation_history=conversation_history,
            ))
            
            return {
                "final_response": response,
                "messages": conversation_history or [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        except Exception as exc:
            import traceback
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
