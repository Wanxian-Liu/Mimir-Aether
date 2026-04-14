"""
SessionManager - Cross-Platform Session Management

Manages user sessions across multiple platforms, maintaining context
and state for each user regardless of which platform they use.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from .message import Message


@dataclass
class Session:
    """
    Represents a user session across platforms.

    A session is uniquely identified by a user_id, but can span
    multiple platforms. The session maintains context and metadata
    about the user's interaction history.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    platform: str = "unknown"
    chat_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    active_platforms: set[str] = field(default_factory=set)
    context: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()

    def is_expired(self, ttl_seconds: float = 3600) -> bool:
        """Check if session has expired based on TTL."""
        return (datetime.utcnow() - self.last_activity_at).total_seconds() > ttl_seconds

    def add_platform(self, platform: str) -> None:
        """Register a platform for this user."""
        self.active_platforms.add(platform)

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dict."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "platform": self.platform,
            "chat_id": self.chat_id,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "active_platforms": list(self.active_platforms),
            "context": self.context,
            "state": self.state,
            "metadata": self.metadata,
        }


class SessionManager:
    """
    Manages user sessions across all platforms.

    Features:
    - Per-user session tracking across platforms
    - Automatic session expiration
    - Context persistence
    - Multi-platform session linking
    """

    def __init__(
        self,
        session_ttl: float = 3600,
        max_sessions: int = 10000,
        cleanup_interval: float = 300,
    ):
        """
        Initialize SessionManager.

        Args:
            session_ttl: Session time-to-live in seconds (default: 1 hour)
            max_sessions: Maximum number of active sessions
            cleanup_interval: Interval for expired session cleanup (seconds)
        """
        self.session_ttl = session_ttl
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval

        # Sessions indexed by session_id
        self._sessions: dict[str, Session] = {}
        # User to session mapping (user can have multiple sessions across platforms)
        self._user_sessions: dict[str, set[str]] = defaultdict(set)
        # Platform + chat_id to session mapping
        self._platform_sessions: dict[tuple[str, str], str] = {}

        self.logger = logging.getLogger("gateway.session")
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the session manager cleanup task."""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("SessionManager started")

    async def stop(self) -> None:
        """Stop the session manager cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self.logger.info("SessionManager stopped")

    async def get_or_create_session(self, message: Message) -> Session:
        """
        Get existing session or create a new one for a message.

        Args:
            message: Incoming message

        Returns:
            Session instance for this user/platform
        """
        if not message.context:
            raise ValueError("Message has no context")

        platform = message.context.platform
        chat_id = message.context.chat_id
        sender_id = message.context.sender_id

        # Check for existing platform session
        key = (platform, chat_id)
        async with self._lock:
            if key in self._platform_sessions:
                session_id = self._platform_sessions[key]
                session = self._sessions.get(session_id)
                if session and not session.is_expired(self.session_ttl):
                    session.touch()
                    return session

            # Create new session
            session = Session(
                user_id=sender_id,
                platform=platform,
                chat_id=chat_id,
            )
            session.add_platform(platform)

            # Check max sessions
            if len(self._sessions) >= self.max_sessions:
                await self._evict_oldest()

            self._sessions[session.id] = session
            self._user_sessions[sender_id].add(session.id)
            self._platform_sessions[key] = session.id

            self.logger.debug(f"Created session {session.id} for user {sender_id} on {platform}")
            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def get_user_sessions(self, user_id: str) -> list[Session]:
        """Get all sessions for a user."""
        async with self._lock:
            session_ids = self._user_sessions.get(user_id, set())
            return [s for s in (self._sessions.get(sid) for sid in session_ids) if s]

    async def link_platform(self, session_id: str, platform: str, chat_id: str) -> None:
        """
        Link another platform to an existing session.

        This allows a user to continue their conversation across platforms.

        Args:
            session_id: Existing session ID
            platform: Platform to link
            chat_id: Chat ID on that platform
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            session.add_platform(platform)
            self._platform_sessions[(platform, chat_id)] = session.id
            self.logger.info(f"Linked {platform}:{chat_id} to session {session_id}")

    async def update_session(
        self,
        session_id: str,
        context: Optional[dict[str, Any]] = None,
        state: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Update session data.

        Args:
            session_id: Session ID to update
            context: Context data to merge
            state: State data to merge
            metadata: Metadata to merge
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            session.touch()

            if context:
                session.context.update(context)
            if state:
                session.state.update(state)
            if metadata:
                session.metadata.update(metadata)

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return False

            self._user_sessions[session.user_id].discard(session_id)
            self._platform_sessions.pop((session.platform, session.chat_id), None)

            self.logger.debug(f"Deleted session {session_id}")
            return True

    async def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        async with self._lock:
            total = len(self._sessions)
            expired = sum(1 for s in self._sessions.values() if s.is_expired(self.session_ttl))
            platform_counts: dict[str, int] = defaultdict(int)
            for s in self._sessions.values():
                platform_counts[s.platform] += 1

            return {
                "total_sessions": total,
                "expired_sessions": expired,
                "active_sessions": total - expired,
                "max_sessions": self.max_sessions,
                "sessions_by_platform": dict(platform_counts),
                "cleanup_interval": self.cleanup_interval,
                "session_ttl": self.session_ttl,
            }

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")

    async def _cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        async with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items()
                if s.is_expired(self.session_ttl)
            ]

            for sid in expired_ids:
                session = self._sessions.pop(sid, None)
                if session:
                    self._user_sessions[session.user_id].discard(sid)
                    self._platform_sessions.pop((session.platform, session.chat_id), None)

            if expired_ids:
                self.logger.info(f"Cleaned up {len(expired_ids)} expired sessions")

            return len(expired_ids)

    async def _evict_oldest(self) -> None:
        """Evict the oldest session when max capacity is reached."""
        if not self._sessions:
            return

        # Find oldest non-expired session
        oldest = min(
            self._sessions.items(),
            key=lambda x: x[1].last_activity_at,
        )
        session_id = oldest[0]

        self.logger.warning(f"Evicting oldest session {session_id} due to capacity limit")
        await self.delete_session(session_id)
