"""M5: explicit port for session / transcript restore (replaceability seam).

Production: ``MimirAetherAgent`` holds a ``SessionRestorePort`` (default
``_BuiltinSessionRestore`` delegating to ``_builtin_restore_session``).
Called once after init to hydrate ``conversation_history`` from the backing
store (Hermes ``SessionDB`` when available).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class SessionRestorePort(Protocol):
    """Sync hook returning whether any transcript was loaded into the agent."""

    def restore_after_init(self, session_id: Optional[str] = None) -> bool:
        ...
