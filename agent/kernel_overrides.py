"""M5: bundle optional kernel backends for one-shot agent construction.

Use when tests or harnesses inject several :class:`~agent.llm_port.LlmInvocationPort` /
:class:`~agent.tool_port.ToolInvocationPort` / … implementations together without
long keyword lists.

Precedence on :class:`~agent.core_loop.MimirAetherAgent`: explicit constructor
arguments override bundle fields; see ``AgentManager.get_agent`` for API layering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AgentKernelOverrides:
    """Optional replaceability backends (any field may be omitted)."""

    llm_backend: Optional[Any] = None
    tool_backend: Optional[Any] = None
    session_backend: Optional[Any] = None
    session_db_factory: Optional[Any] = None
    checkpoint_backend: Optional[Any] = None
