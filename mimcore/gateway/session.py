"""MimCore gateway session - re-export SessionDB from hermes_state.

This module provides the SessionDB class for SQLite-backed session storage,
mirroring the hermes_state.SessionDB interface.
"""

from hermes_state import SessionDB

__all__ = ["SessionDB"]
