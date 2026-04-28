"""MimirAether AIAgent compatibility stub.

This module provides a minimal AIAgent stub for the ACP adapter.
Full AIAgent implementation is tracked in MimirAether development.
"""

import threading
from typing import Any, Dict, List, Optional


class AIAgent:
    """Minimal stub for AIAgent interface required by ACP adapter.

    This stub allows the ACP adapter to import and instantiate AIAgent
    without errors. Full agent functionality (run_conversation, tool
    callbacks, etc.) requires the complete AIAgent implementation.
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
        self.model = model
        self.provider = provider
        self.api_mode = api_mode
        self.base_url = base_url
        self.api_key = api_key
        self.command = command
        self.args = args or []

        # Callback hooks (set by ACP server)
        self.tool_progress_callback: Optional[Any] = None
        self.thinking_callback: Optional[Any] = None
        self.step_callback: Optional[Any] = None
        self.message_callback: Optional[Any] = None

        # Tool surface (set after MCP server registration)
        self.tools: Optional[List[Dict[str, Any]]] = None
        self.valid_tool_names: Optional[set] = None

        # Print function (set by ACP session manager)
        self._print_fn: Any = lambda *a, **kw: None

        # Interrupt support
        self._interrupt_event: Optional[threading.Event] = None

    def interrupt(self) -> None:
        """Request the agent to interrupt current execution."""
        if self._interrupt_event:
            self._interrupt_event.set()

    def _invalidate_system_prompt(self) -> None:
        """Invalidate cached system prompt (called after tool surface changes)."""
        pass

    def run_conversation(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        task_id: str,
    ) -> Dict[str, Any]:
        """Stub: return a basic error response.

        Full implementation requires the complete AIAgent class.
        """
        return {
            "final_response": "[AIAgent stub] Agent not yet implemented in MimirAether.",
            "messages": conversation_history,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


def main() -> None:
    """CLI entry point (stub)."""
    print("MimirAether AIAgent stub — use 'python -m acp_adapter.entry' for ACP server")
