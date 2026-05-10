"""MimirAether AIAgent — wraps MimirAetherAgent for gateway compatibility."""

import threading
from typing import Any, Dict, List, Optional


class AIAgent:
    """AIAgent wrapper for MimirAetherAgent, compatible with gateway interface.

    Delegates all agent functionality to the real MimirAetherAgent
    in agent.core_loop.
    """

    def __init__(
        self,
        platform: str = "acp",
        enabled_toolsets: Optional[List[str]] = None,
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
            )
        return self._real_agent

    def interrupt(self) -> None:
        """Request the agent to interrupt current execution."""
        if self._interrupt_event:
            self._interrupt_event.set()
        if self._real_agent and hasattr(self._real_agent, 'interrupt'):
            self._real_agent.interrupt()

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
            response = asyncio.run(agent.run_conversation(user_message))
            
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
