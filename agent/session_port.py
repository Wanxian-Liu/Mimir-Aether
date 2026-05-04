"""M5: explicit ports for session store / transcript restore (replaceability seams).

- ``SessionRestorePort``: hydrate ``conversation_history`` after init (default
  ``_BuiltinSessionRestore`` → ``_builtin_restore_session``).
- ``SessionDbClientFactory``: create the Hermes-compatible store client used by
  ``InsightsEngine`` (SQL mode) and by the builtin restore path (default
  ``_BuiltinSessionDbFactory`` → ``SessionDB()`` when the class is available).
  The same protocol is used by ``gateway.run.GatewayRunner(..., session_db_factory=)``
  to inject the SQLite store used for titles, branching, and ``session_db=`` passed
  to the Hermes ``AIAgent``.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class SessionRestorePort(Protocol):
    """Sync hook returning whether any transcript was loaded into the agent."""

    def restore_after_init(self, session_id: Optional[str] = None) -> bool:
        ...


@runtime_checkable
class SessionDbClientFactory(Protocol):
    """Return a new SessionDB-compatible client, or ``None`` for memory-only insights / no restore."""

    def create_session_db(self) -> Optional[Any]:
        ...
