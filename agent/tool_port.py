"""M5: explicit port for tool batch execution (replaceability seam).

Production: ``MimirAetherAgent`` holds a ``ToolInvocationPort`` (default
``_BuiltinToolBackend`` delegating to ``_builtin_execute_tools``).
Alternate implementations can record, sandbox, or route tool calls without
changing call sites that use ``_execute_tools``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable

from .types import ToolResult


@runtime_checkable
class ToolInvocationPort(Protocol):
    """Async batch executor returning ``ToolResult`` list (same contract as ``_execute_tools``)."""

    async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0) -> List[ToolResult]:
        ...
