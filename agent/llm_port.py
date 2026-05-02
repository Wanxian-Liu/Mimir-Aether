"""M5: explicit port for model invocation (replaceability seam).

Production: ``MimirAetherAgent`` holds a ``LlmInvocationPort`` (default
``_BuiltinLlmBackend`` delegating to ``_builtin_call_model_with_tokens``).
Tests often patch ``_call_model_with_tokens`` with async callables. This module names the contract
so alternate implementations can be type-checked without changing test semantics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class LlmInvocationPort(Protocol):
    """Async entry that returns ``(response_dict, latency_ms)`` like ``_call_model_with_tokens``."""

    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        ...
