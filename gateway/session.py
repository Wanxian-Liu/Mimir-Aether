"""
Session management for the gateway.

Handles:
- Session context tracking (where messages come from)
- Session storage (conversations persisted to disk)
- Reset policy evaluation (when to start fresh)
- Dynamic system prompt injection (agent knows its context)

# 来源: hermes-agent/gateway/session.py (已改造为MimirAether)
# 改造点:
#   1. 移除 hermes_state.SessionDB 依赖 → 自研 SQLite/OpenClaw 持久化层
#   2. 适配 OpenClaw 配置结构 (~/.openclaw/)
#   3. 保持 PII 处理逻辑（用户ID哈希、聊天ID哈希）
#   4. 保持 reset policy 逻辑（idle/daily/both/none）
#   5. 移除 Hermes 品牌标识
"""

import hashlib
import logging
import os
import json
import threading
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now() -> datetime:
    """Return the current local time."""
    return datetime.now()


# ---------------------------------------------------------------------------
# PII redaction helpers
# ---------------------------------------------------------------------------

def _hash_id(value: str) -> str:
    """Deterministic 12-char hex hash of an identifier."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _hash_sender_id(value: str) -> str:
    """Hash a sender ID to ``user_<12hex>``."""
    return f"user_{_hash_id(value)}"


def _hash_chat_id(value: str) -> str:
    """Hash the numeric portion of a chat ID, preserving platform prefix.

    ``telegram:12345`` → ``telegram:<hash>``
    ``12345``          → ``<hash>``
    """
    colon = value.find(":")
    if colon > 0:
        prefix = value[:colon]
        return f"{prefix}:{_hash_id(value[colon + 1:])}"
    return _hash_id(value)


# Platform等已从config.py导入
from .config import (
    Platform,
    GatewayConfig,
    SessionResetPolicy,  # noqa: F401 — re-exported via gateway/__init__.py
    HomeChannel,
)


@dataclass
class SessionSource:
    """
    Describes where a message originated from.
    
    This information is used to:
    1. Route responses back to the right place
    2. Inject context into the system prompt
    3. Track origin for cron job delivery
    """
    platform: Platform
    chat_id: str
    chat_name: Optional[str] = None
    chat_type: str = "dm"  # "dm", "group", "channel", "thread"
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    thread_id: Optional[str] = None  # For forum topics, Discord threads, etc.
    chat_topic: Optional[str] = None  # Channel topic/description (Discord, Slack)
    user_id_alt: Optional[str] = None  # Signal UUID (alternative to phone number)
    chat_id_alt: Optional[str] = None  # Signal group internal ID
    
    @property
    def description(self) -> str:
        """Human-readable description of the source."""
        if self.platform == Platform.LOCAL:
            return "CLI terminal"
        
        parts = []
        if self.chat_type == "dm":
            parts.append(f"DM with {self.user_name or self.user_id or 'user'}")
        elif self.chat_type == "group":
            parts.append(f"group: {self.chat_name or self.chat_id}")
        elif self.chat_type == "channel":
            parts.append(f"channel: {self.chat_name or self.chat_id}")
        else:
            parts.append(self.chat_name or self.chat_id)
        
        if self.thread_id:
            parts.append(f"thread: {self.thread_id}")
        
        return ", ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "platform": self.platform.value,
            "chat_id": self.chat_id,
            "chat_name": self.chat_name,
            "chat_type": self.chat_type,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "thread_id": self.thread_id,
            "chat_topic": self.chat_topic,
        }
        if self.user_id_alt:
            d["user_id_alt"] = self.user_id_alt
        if self.chat_id_alt:
            d["chat_id_alt"] = self.chat_id_alt
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSource":
        return cls(
            platform=Platform(data["platform"]),
            chat_id=str(data["chat_id"]),
            chat_name=data.get("chat_name"),
            chat_type=data.get("chat_type", "dm"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            thread_id=data.get("thread_id"),
            chat_topic=data.get("chat_topic"),
            user_id_alt=data.get("user_id_alt"),
            chat_id_alt=data.get("chat_id_alt"),
        )
    


@dataclass
class SessionContext:
    """
    Full context for a session, used for dynamic system prompt injection.
    
    The agent receives this information to understand:
    - Where messages are coming from
    - What platforms are available
    - Where it can deliver scheduled task outputs
    """
    source: SessionSource
    connected_platforms: List[Platform]
    home_channels: Dict[Platform, HomeChannel]
    
    # Session metadata
    session_key: str = ""
    session_id: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "connected_platforms": [p.value for p in self.connected_platforms],
            "home_channels": {
                p.value: hc.to_dict() for p, hc in self.home_channels.items()
            },
            "session_key": self.session_key,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


_PII_SAFE_PLATFORMS = frozenset({
    Platform.WHATSAPP,
    Platform.SIGNAL,
    Platform.TELEGRAM,
    Platform.BLUEBUBBLES,
})
"""Platforms where user IDs can be safely redacted (no in-message mention system
that requires raw IDs).  Discord is excluded because mentions use ``<@user_id>``
and the LLM needs the real ID to tag users."""


def build_session_context_prompt(
    context: SessionContext,
    *,
    redact_pii: bool = False,
) -> str:
    """
    Build the dynamic system prompt section that tells the agent about its context.
    
    This is injected into the system prompt so the agent knows:
    - Where messages are coming from
    - What platforms are connected
    - Where it can deliver scheduled task outputs

    When *redact_pii* is True **and** the source platform is in
    ``_PII_SAFE_PLATFORMS``, phone numbers are stripped and user/chat IDs
    are replaced with deterministic hashes before being sent to the LLM.
    Platforms like Discord are excluded because mentions need real IDs.
    Routing still uses the original values (they stay in SessionSource).
    """
    # Only apply redaction on platforms where IDs aren't needed for mentions
    redact_pii = redact_pii and context.source.platform in _PII_SAFE_PLATFORMS
    lines = [
        "## Current Session Context",
        "",
    ]
    
    # Source info
    platform_name = context.source.platform.value.title()
    if context.source.platform == Platform.LOCAL:
        lines.append(f"**Source:** {platform_name} (the machine running this agent)")
    else:
        # Build a description that respects PII redaction
        src = context.source
        if redact_pii:
            # Build a safe description without raw IDs
            _uname = src.user_name or (
                _hash_sender_id(src.user_id) if src.user_id else "user"
            )
            _cname = src.chat_name or _hash_chat_id(src.chat_id)
            if src.chat_type == "dm":
                desc = f"DM with {_uname}"
            elif src.chat_type == "group":
                desc = f"group: {_cname}"
            elif src.chat_type == "channel":
                desc = f"channel: {_cname}"
            else:
                desc = _cname
        else:
            desc = src.description
        lines.append(f"**Source:** {platform_name} ({desc})")
    
    # Channel topic (if available - provides context about the channel's purpose)
    if context.source.chat_topic:
        lines.append(f"**Channel Topic:** {context.source.chat_topic}")

    # User identity.
    # In shared thread sessions (non-DM with thread_id), multiple users
    # contribute to the same conversation.  Don't pin a single user name
    # in the system prompt — it changes per-turn and would bust the prompt
    # cache.  Instead, note that this is a multi-user thread; individual
    # sender names are prefixed on each user message by the gateway.
    _is_shared_thread = (
        context.source.chat_type != "dm"
        and context.source.thread_id
    )
    if _is_shared_thread:
        lines.append(
            "**Session type:** Multi-user thread — messages are prefixed "
            "with [sender name]. Multiple users may participate."
        )
    elif context.source.user_name:
        lines.append(f"**User:** {context.source.user_name}")
    elif context.source.user_id:
        uid = context.source.user_id
        if redact_pii:
            uid = _hash_sender_id(uid)
        lines.append(f"**User ID:** {uid}")
    
    # Platform-specific behavioral notes
    if context.source.platform == Platform.SLACK:
        lines.append("")
        lines.append(
            "**Platform notes:** You are running inside Slack. "
            "You do NOT have access to Slack-specific APIs — you cannot search "
            "channel history, pin/unpin messages, manage channels, or list users. "
            "Do not promise to perform these actions. If the user asks, explain "
            "that you can only read messages sent directly to you and respond."
        )
    elif context.source.platform == Platform.DISCORD:
        lines.append("")
        lines.append(
            "**Platform notes:** You are running inside Discord. "
            "You do NOT have access to Discord-specific APIs — you cannot search "
            "channel history, pin messages, manage roles, or list server members. "
            "Do not promise to perform these actions. If the user asks, explain "
            "that you can only read messages sent directly to you and respond."
        )

    # Connected platforms
    platforms_list = ["local (files on this machine)"]
    for p in context.connected_platforms:
        if p != Platform.LOCAL:
            platforms_list.append(f"{p.value}: Connected ✓")
    
    lines.append(f"**Connected Platforms:** {', '.join(platforms_list)}")
    
    # Home channels
    if context.home_channels:
        lines.append("")
        lines.append("**Home Channels (default destinations):**")
        for platform, home in context.home_channels.items():
            hc_id = _hash_chat_id(home.chat_id) if redact_pii else home.chat_id
            lines.append(f"  - {platform.value}: {home.name} (ID: {hc_id})")
    
    # Delivery options for scheduled tasks
    lines.append("")
    lines.append("**Delivery options for scheduled tasks:**")
    
    # Origin delivery
    if context.source.platform == Platform.LOCAL:
        lines.append("- `\"origin\"` → Local output (saved to files)")
    else:
        _origin_label = context.source.chat_name or (
            _hash_chat_id(context.source.chat_id) if redact_pii else context.source.chat_id
        )
        lines.append(f"- `\"origin\"` → Back to this chat ({_origin_label})")
    
    # Local always available
    lines.append(
        '- `"local"` → Save to local files only ($MIMIR_AETHER_HOME/cron/output/)'
    )
    
    # Platform home channels
    for platform, home in context.home_channels.items():
        lines.append(f"- `\"{platform.value}\"` → Home channel ({home.name})")
    
    # Note about explicit targeting
    lines.append("")
    lines.append("*For explicit targeting, use `\"platform:chat_id\"` format if the user provides a specific chat ID.*")
    
    return "\n".join(lines)


@dataclass
class SessionEntry:
    """
    Entry in the session store.
    
    Maps a session key to its current session ID and metadata.
    """
    session_key: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    
    # Origin metadata for delivery routing
    origin: Optional[SessionSource] = None
    
    # Display metadata
    display_name: Optional[str] = None
    platform: Optional[Platform] = None
    chat_type: str = "dm"
    
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_status: str = "unknown"
    
    # Last API-reported prompt tokens (for accurate compression pre-check)
    last_prompt_tokens: int = 0
    
    # Set when a session was created because the previous one expired;
    # consumed once by the message handler to inject a notice into context
    was_auto_reset: bool = False
    auto_reset_reason: Optional[str] = None  # "idle" or "daily"
    reset_had_activity: bool = False  # whether the expired session had any messages
    
    # Set by the background expiry watcher after it successfully flushes
    # memories for this session.  Persisted to sessions.json so the flag
    # survives gateway restarts (the old in-memory _pre_flushed_sessions
    # set was lost on restart, causing redundant re-flushes).
    memory_flushed: bool = False

    # When True the next call to get_or_create_session() will auto-reset
    # this session (create a new session_id) so the user starts fresh.
    # Set by /stop to break stuck-resume loops (#7536).
    suspended: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "session_key": self.session_key,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "display_name": self.display_name,
            "platform": self.platform.value if self.platform else None,
            "chat_type": self.chat_type,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.total_tokens,
            "last_prompt_tokens": self.last_prompt_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "cost_status": self.cost_status,
            "memory_flushed": self.memory_flushed,
            "suspended": self.suspended,
        }
        if self.origin:
            result["origin"] = self.origin.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionEntry":
        origin = None
        if "origin" in data and data["origin"]:
            origin = SessionSource.from_dict(data["origin"])
        
        platform = None
        if data.get("platform"):
            try:
                platform = Platform(data["platform"])
            except ValueError as e:
                logger.debug("Unknown platform value %r: %s", data["platform"], e)
        
        return cls(
            session_key=data["session_key"],
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            origin=origin,
            display_name=data.get("display_name"),
            platform=platform,
            chat_type=data.get("chat_type", "dm"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_read_tokens=data.get("cache_read_tokens", 0),
            cache_write_tokens=data.get("cache_write_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            last_prompt_tokens=data.get("last_prompt_tokens", 0),
            estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
            cost_status=data.get("cost_status", "unknown"),
            memory_flushed=data.get("memory_flushed", False),
            suspended=data.get("suspended", False),
        )


def build_session_key(
    source: SessionSource,
    group_sessions_per_user: bool = True,
    thread_sessions_per_user: bool = False,
) -> str:
    """Build a deterministic session key from a message source.

    This is the single source of truth for session key construction.

    DM rules:
      - DMs include chat_id when present, so each private conversation is isolated.
      - thread_id further differentiates threaded DMs within the same DM chat.
      - Without chat_id, thread_id is used as a best-effort fallback.
      - Without thread_id or chat_id, DMs share a single session.

    Group/channel rules:
      - chat_id identifies the parent group/channel.
      - user_id/user_id_alt isolates participants within that parent chat when available when
        ``group_sessions_per_user`` is enabled.
      - thread_id differentiates threads within that parent chat.  When
        ``thread_sessions_per_user`` is False (default), threads are *shared* across all
        participants — user_id is NOT appended, so every user in the thread
        shares a single session.  This is the expected UX for threaded
        conversations (Telegram forum topics, Discord threads, Slack threads).
      - Without participant identifiers, or when isolation is disabled, messages fall back to one
        shared session per chat.
      - Without identifiers, messages fall back to one session per platform/chat_type.
    """
    platform = source.platform.value
    if source.chat_type == "dm":
        if source.chat_id:
            if source.thread_id:
                return f"agent:main:{platform}:dm:{source.chat_id}:{source.thread_id}"
            return f"agent:main:{platform}:dm:{source.chat_id}"
        if source.thread_id:
            return f"agent:main:{platform}:dm:{source.thread_id}"
        return f"agent:main:{platform}:dm"

    participant_id = source.user_id_alt or source.user_id
    key_parts = ["agent:main", platform, source.chat_type]

    if source.chat_id:
        key_parts.append(source.chat_id)
    if source.thread_id:
        key_parts.append(source.thread_id)

    # In threads, default to shared sessions (all participants see the same
    # conversation).  Per-user isolation only applies when explicitly enabled
    # via thread_sessions_per_user, or when there is no thread (regular group).
    isolate_user = group_sessions_per_user
    if source.thread_id and not thread_sessions_per_user:
        isolate_user = False

    if isolate_user and participant_id:
        key_parts.append(str(participant_id))

    return ":".join(key_parts)


def _append_transcript_dict_to_session_db(db: Any, session_id: str, message: Dict[str, Any]) -> None:
    """Map a JSONL-style transcript row to ``SessionDB.append_message`` (best-effort)."""
    role = str(message.get("role") or "user")
    content = message.get("content")
    if content is None:
        if role == "session_meta":
            payload = {k: v for k, v in message.items() if k != "timestamp"}
            content = json.dumps(payload, ensure_ascii=False)
        else:
            content = ""
    elif not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    tool_name = message.get("tool_name") or message.get("name")
    tool_calls = message.get("tool_calls")
    tool_call_id = message.get("tool_call_id")
    reasoning = message.get("reasoning")
    db.append_message(
        session_id=session_id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        reasoning=reasoning,
    )


class SessionStore:
    """
    Manages session storage and retrieval.

    Uses JSON file storage (sessions.json) for session metadata.
    Message transcripts default to legacy JSONL files per session.

    When ``transcript_session_db`` is set (typically the gateway runner's shared
    ``hermes_state.SessionDB``), ``append_to_transcript`` also appends to SQLite
    unless ``skip_db=True`` — aligning gateway JSONL with Hermes-compatible storage.
    ``rewrite_transcript`` overwrites JSONL and, when ``_db`` is set, calls
    ``clear_messages(session_id)`` then re-appends each message (same mapping as
    ``append_to_transcript``).
    """

    def __init__(
        self,
        sessions_dir: Path,
        config: GatewayConfig,
        has_active_processes_fn=None,
        transcript_session_db: Optional[Any] = None,
    ):
        self.sessions_dir = sessions_dir
        self.config = config
        self._entries: Dict[str, SessionEntry] = {}
        self._loaded = False
        self._lock = threading.Lock()
        self._has_active_processes_fn = has_active_processes_fn

        #: Optional SQLite store for transcript dual-write (same object as ``GatewayRunner._session_db``).
        self._db = transcript_session_db
    
    def _ensure_loaded(self) -> None:
        """Load sessions index from disk if not already loaded."""
        with self._lock:
            self._ensure_loaded_locked()

    def _ensure_loaded_locked(self) -> None:
        """Load sessions index from disk. Must be called with self._lock held."""
        if self._loaded:
            return

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        sessions_file = self.sessions_dir / "sessions.json"

        if sessions_file.exists():
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, entry_data in data.items():
                        try:
                            self._entries[key] = SessionEntry.from_dict(entry_data)
                        except (ValueError, KeyError):
                            # Skip entries with unknown/removed platform values
                            continue
            except Exception as e:
                print(f"[gateway] Warning: Failed to load sessions: {e}")

        self._loaded = True
    
    def _save(self) -> None:
        """Save sessions index to disk (kept for session key -> ID mapping)."""
        import tempfile
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        sessions_file = self.sessions_dir / "sessions.json"

        data = {key: entry.to_dict() for key, entry in self._entries.items()}
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.sessions_dir), suffix=".tmp", prefix=".sessions_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, sessions_file)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.debug("Could not remove temp file %s: %s", tmp_path, e)
            raise
    
    def _generate_session_key(self, source: SessionSource) -> str:
        """Generate a session key from a source."""
        return build_session_key(
            source,
            group_sessions_per_user=getattr(self.config, "group_sessions_per_user", True),
            thread_sessions_per_user=getattr(self.config, "thread_sessions_per_user", False),
        )
    
    def _is_session_expired(self, entry: SessionEntry) -> bool:
        """Check if a session has expired based on its reset policy.
        
        Works from the entry alone — no SessionSource needed.
        Used by the background expiry watcher to proactively flush memories.
        Sessions with active background processes are never considered expired.
        """
        if self._has_active_processes_fn:
            if self._has_active_processes_fn(entry.session_key):
                return False

        policy = self.config.get_reset_policy(
            platform=entry.platform,
            session_type=entry.chat_type,
        )

        if policy.mode == "none":
            return False

        now = _now()

        if policy.mode in ("idle", "both"):
            idle_deadline = entry.updated_at + timedelta(minutes=policy.idle_minutes)
            if now > idle_deadline:
                return True

        if policy.mode in ("daily", "both"):
            today_reset = now.replace(
                hour=policy.at_hour,
                minute=0, second=0, microsecond=0,
            )
            if now.hour < policy.at_hour:
                today_reset -= timedelta(days=1)
            if entry.updated_at < today_reset:
                return True

        return False

    def _should_reset(self, entry: SessionEntry, source: SessionSource) -> Optional[str]:
        """
        Check if a session should be reset based on policy.
        
        Returns the reset reason ("idle" or "daily") if a reset is needed,
        or None if the session is still valid.
        
        Sessions with active background processes are never reset.
        """
        if self._has_active_processes_fn:
            session_key = self._generate_session_key(source)
            if self._has_active_processes_fn(session_key):
                return None

        policy = self.config.get_reset_policy(
            platform=source.platform,
            session_type=source.chat_type
        )
        
        if policy.mode == "none":
            return None
        
        now = _now()
        
        if policy.mode in ("idle", "both"):
            idle_deadline = entry.updated_at + timedelta(minutes=policy.idle_minutes)
            if now > idle_deadline:
                return "idle"
        
        if policy.mode in ("daily", "both"):
            today_reset = now.replace(
                hour=policy.at_hour, 
                minute=0, 
                second=0, 
                microsecond=0
            )
            if now.hour < policy.at_hour:
                today_reset -= timedelta(days=1)
            
            if entry.updated_at < today_reset:
                return "daily"
        
        return None
    
    def has_any_sessions(self) -> bool:
        """Check if any sessions have ever been created (across all platforms).

        # SQLite已移除
        # 原始: 使用 SQLite session_count() > 1 判断
        # 自研: 可以继续使用 sessions.json 的条目数判断
        #       注意: sessions.json 只记录当前活跃 session，重置后会覆盖
        #            可能需要额外机制记录历史会话数

        Uses the in-memory entries as source of truth for active sessions.
        Falls back to sessions.json entry count for historical check.
        """
        # Fallback: check if sessions.json was loaded with existing data.
        with self._lock:
            self._ensure_loaded_locked()
            return len(self._entries) > 1

    def get_or_create_session(
        self,
        source: SessionSource,
        force_new: bool = False
    ) -> SessionEntry:
        """
        Get an existing session or create a new one.

        Evaluates reset policy to determine if the existing session is stale.
        # SQLite已移除
        """
        session_key = self._generate_session_key(source)
        now = _now()

        # SQLite已移除, 使用JSONL
        # All _entries / _loaded mutations are protected by self._lock.
        db_end_session_id = None
        db_create_kwargs = None

        with self._lock:
            self._ensure_loaded_locked()

            if session_key in self._entries and not force_new:
                entry = self._entries[session_key]

                # Auto-reset sessions marked as suspended (e.g. after /stop
                # broke a stuck loop — #7536).
                if entry.suspended:
                    reset_reason = "suspended"
                else:
                    reset_reason = self._should_reset(entry, source)
                if not reset_reason:
                    entry.updated_at = now
                    self._save()
                    return entry
                else:
                    # Session is being auto-reset.
                    was_auto_reset = True
                    auto_reset_reason = reset_reason
                    # Track whether the expired session had any real conversation
                    reset_had_activity = entry.total_tokens > 0
                    db_end_session_id = entry.session_id  # SQLite end_session已移除
            else:
                was_auto_reset = False
                auto_reset_reason = None
                reset_had_activity = False

            # Create new session
            session_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            entry = SessionEntry(
                session_key=session_key,
                session_id=session_id,
                created_at=now,
                updated_at=now,
                origin=source,
                display_name=source.chat_name,
                platform=source.platform,
                chat_type=source.chat_type,
                was_auto_reset=was_auto_reset,
                auto_reset_reason=auto_reset_reason,
                reset_had_activity=reset_had_activity,
            )

            self._entries[session_key] = entry
            self._save()
            db_create_kwargs = {
                "session_id": session_id,
                "source": source.platform.value,
                "user_id": source.user_id,
            }

        # SQLite operations已移除
        # if self._db and db_end_session_id:
        #     try:
        #         self._db.end_session(db_end_session_id, "session_reset")
        #     except Exception as e:
        #         logger.debug("Session DB operation failed: %s", e)
        #
        # if self._db and db_create_kwargs:
        #     try:
        #         self._db.create_session(**db_create_kwargs)
        #     except Exception as e:
        #         print(f"[gateway] Warning: Failed to create SQLite session: {e}")

        return entry

    def update_session(
        self,
        session_key: str,
        last_prompt_tokens: int = None,
    ) -> None:
        """Update lightweight session metadata after an interaction."""
        with self._lock:
            self._ensure_loaded_locked()

            if session_key in self._entries:
                entry = self._entries[session_key]
                entry.updated_at = _now()
                if last_prompt_tokens is not None:
                    entry.last_prompt_tokens = last_prompt_tokens
                self._save()

    def suspend_session(self, session_key: str) -> bool:
        """Mark a session as suspended so it auto-resets on next access.

        Used by ``/stop`` to prevent stuck sessions from being resumed
        after a gateway restart (#7536).  Returns True if the session
        existed and was marked.
        """
        with self._lock:
            self._ensure_loaded_locked()
            if session_key in self._entries:
                self._entries[session_key].suspended = True
                self._save()
                return True
        return False

    def suspend_recently_active(self, max_age_seconds: int = 120) -> int:
        """Mark recently-active sessions as suspended.

        Called on gateway startup to prevent sessions that were likely
        in-flight when the gateway last exited from being blindly resumed
        (#7536).  Only suspends sessions updated within *max_age_seconds*
        to avoid resetting long-idle sessions that are harmless to resume.
        Returns the number of sessions that were suspended.
        """
        from datetime import timedelta

        cutoff = _now() - timedelta(seconds=max_age_seconds)
        count = 0
        with self._lock:
            self._ensure_loaded_locked()
            for entry in self._entries.values():
                if not entry.suspended and entry.updated_at >= cutoff:
                    entry.suspended = True
                    count += 1
            if count:
                self._save()
        return count

    def reset_session(self, session_key: str) -> Optional[SessionEntry]:
        """Force reset a session, creating a new session ID."""
        db_end_session_id = None  # SQLite已移除
        db_create_kwargs = None  # SQLite已移除
        new_entry = None

        with self._lock:
            self._ensure_loaded_locked()

            if session_key not in self._entries:
                return None

            old_entry = self._entries[session_key]
            db_end_session_id = old_entry.session_id  # SQLite已移除

            now = _now()
            session_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            new_entry = SessionEntry(
                session_key=session_key,
                session_id=session_id,
                created_at=now,
                updated_at=now,
                origin=old_entry.origin,
                display_name=old_entry.display_name,
                platform=old_entry.platform,
                chat_type=old_entry.chat_type,
            )

            self._entries[session_key] = new_entry
            self._save()
            db_create_kwargs = {
                "session_id": session_id,
                "source": old_entry.platform.value if old_entry.platform else "unknown",
                "user_id": old_entry.origin.user_id if old_entry.origin else None,
            }

        # SQLite operations已移除
        # if self._db and db_end_session_id:
        #     try:
        #         self._db.end_session(db_end_session_id, "session_reset")
        #     except Exception as e:
        #         logger.debug("Session DB operation failed: %s", e)
        #
        # if self._db and db_create_kwargs:
        #     try:
        #         self._db.create_session(**db_create_kwargs)
        #     except Exception as e:
        #         logger.debug("Session DB operation failed: %s", e)

        return new_entry

    def switch_session(self, session_key: str, target_session_id: str) -> Optional[SessionEntry]:
        """Switch a session key to point at an existing session ID.

        Used by ``/resume`` to restore a previously-named session.
        # SQLite reopen_session已移除
        """
        db_end_session_id = None  # SQLite已移除
        new_entry = None

        with self._lock:
            self._ensure_loaded_locked()

            if session_key not in self._entries:
                return None

            old_entry = self._entries[session_key]

            # Don't switch if already on that session
            if old_entry.session_id == target_session_id:
                return old_entry

            db_end_session_id = old_entry.session_id  # SQLite已移除

            now = _now()
            new_entry = SessionEntry(
                session_key=session_key,
                session_id=target_session_id,
                created_at=now,
                updated_at=now,
                origin=old_entry.origin,
                display_name=old_entry.display_name,
                platform=old_entry.platform,
                chat_type=old_entry.chat_type,
            )

            self._entries[session_key] = new_entry
            self._save()

        # SQLite operations已移除
        # if self._db and db_end_session_id:
        #     try:
        #         self._db.end_session(db_end_session_id, "session_switch")
        #     except Exception as e:
        #         logger.debug("Session DB end_session failed: %s", e)
        #
        # if self._db:
        #     try:
        #         self._db.reopen_session(target_session_id)
        #     except Exception as e:
        #         logger.debug("Session DB reopen_session failed: %s", e)

        return new_entry

    def list_sessions(self, active_minutes: Optional[int] = None) -> List[SessionEntry]:
        """List all sessions, optionally filtered by activity."""
        with self._lock:
            self._ensure_loaded_locked()
            entries = list(self._entries.values())

        if active_minutes is not None:
            cutoff = _now() - timedelta(minutes=active_minutes)
            entries = [e for e in entries if e.updated_at >= cutoff]

        entries.sort(key=lambda e: e.updated_at, reverse=True)

        return entries
    
    def get_transcript_path(self, session_id: str) -> Path:
        """Get the path to a session's legacy transcript file."""
        return self.sessions_dir / f"{session_id}.jsonl"
    
    def append_to_transcript(self, session_id: str, message: Dict[str, Any], skip_db: bool = False) -> None:
        """Append a message to a session's transcript (JSONL; optional SQLite dual-write).

        Args:
            skip_db: When True, only write to JSONL and skip the SQLite write.
        """
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = self.get_transcript_path(session_id)
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")

        if self._db and not skip_db:
            try:
                _append_transcript_dict_to_session_db(self._db, session_id, message)
            except Exception as e:
                logger.debug("Session DB transcript append failed: %s", e)
    
    def rewrite_transcript(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Replace the entire transcript for a session with new messages.

        Used by /retry, /undo, and /compress to persist modified conversation history.
        Writes JSONL, then when ``self._db`` is set: ``clear_messages`` (if present)
        and re-append each row to SQLite using the same mapping as
        ``append_to_transcript``.
        """
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = self.get_transcript_path(session_id)
        with open(transcript_path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        if self._db:
            try:
                clear = getattr(self._db, "clear_messages", None)
                if not callable(clear):
                    logger.debug(
                        "Session DB has no clear_messages; SQLite rewrite skipped for %s",
                        session_id,
                    )
                else:
                    clear(session_id)
                    for msg in messages:
                        _append_transcript_dict_to_session_db(self._db, session_id, msg)
            except Exception as e:
                logger.debug("Session DB transcript rewrite failed: %s", e)

    def load_transcript(self, session_id: str) -> List[Dict[str, Any]]:
        """Load all messages from a session's transcript.
        
        # SQLite已移除, 仅使用JSONL
        """
        # Load JSONL transcript
        transcript_path = self.get_transcript_path(session_id)
        jsonl_messages = []
        if transcript_path.exists():
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            jsonl_messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(
                                "Skipping corrupt line in transcript %s: %s",
                                session_id, line[:120],
                            )

        return jsonl_messages


def build_session_context(
    source: SessionSource,
    config: GatewayConfig,
    session_entry: Optional[SessionEntry] = None
) -> SessionContext:
    """
    Build a full session context from a source and config.
    
    This is used to inject context into the agent's system prompt.
    """
    connected = config.get_connected_platforms()
    
    home_channels = {}
    for platform in connected:
        home = config.get_home_channel(platform)
        if home:
            home_channels[platform] = home
    
    context = SessionContext(
        source=source,
        connected_platforms=connected,
        home_channels=home_channels,
    )
    
    if session_entry:
        context.session_key = session_entry.session_key
        context.session_id = session_entry.session_id
        context.created_at = session_entry.created_at
        context.updated_at = session_entry.updated_at
    
    return context


# ---------------------------------------------------------------------------
# Backward compatibility aliases (for router.py and __init__.py)
# These map the old MimirAether names to the new hermes-derived names
# ---------------------------------------------------------------------------
Session = SessionEntry  # type: ignore[misc, assignment]  # Backward compat: old Session -> new SessionEntry

# ---------------------------------------------------------------------------
# SessionManager compatibility adapter
# Old MimirAether SessionManager worked with Message objects.
# This thin adapter bridges to the hermes SessionStore which uses SessionSource.
# ---------------------------------------------------------------------------
class SessionManager:
    """
    Compatibility adapter wrapping hermes-style SessionStore.
    
    Provides the same interface as the old in-memory SessionManager:
    - get_or_create_session(message) -> SessionEntry
    - update_session(session_key, ...) -> None
    - suspend_session(session_key) -> bool
    - list_sessions(...) -> list
    
    The underlying SessionStore handles reset policy, PII, token tracking, etc.
    """
    
    def __init__(self, sessions_dir, config, has_active_processes_fn=None):
        # Use threading lock for sync access (router uses async, but we wrap)
        self._store = SessionStore(sessions_dir, config, has_active_processes_fn)
    
    def get_or_create_session(self, message) -> SessionEntry:
        """Get or create session from a Message object."""
        from .message import MessageContext
        from .config import Platform
        
        ctx = message.context
        # Build SessionSource from MessageContext
        source = SessionSource(
            platform=Platform(ctx.platform.value),
            chat_id=ctx.chat_id,
            chat_name=getattr(ctx, 'chat_name', None),
            chat_type=getattr(ctx, 'chat_type', 'dm'),
            user_id=ctx.sender_id,
            user_name=getattr(ctx, 'sender_name', None),
            thread_id=getattr(ctx, 'thread_id', None),
        )
        return self._store.get_or_create_session(source)
    
    def update_session(self, session_key: str, last_prompt_tokens: int = None) -> None:
        self._store.update_session(session_key, last_prompt_tokens)
    
    def suspend_session(self, session_key: str) -> bool:
        return self._store.suspend_session(session_key)
    
    def suspend_recently_active(self, max_age_seconds: int = 120) -> int:
        return self._store.suspend_recently_active(max_age_seconds)
    
    def list_sessions(self, active_minutes=None) -> list:
        return self._store.list_sessions(active_minutes)
    
    def get_transcript_path(self, session_id: str):
        return self._store.get_transcript_path(session_id)
    
    def append_to_transcript(self, session_id: str, message: dict, skip_db: bool = False) -> None:
        self._store.append_to_transcript(session_id, message, skip_db)
    
    def rewrite_transcript(self, session_id: str, messages: list) -> None:
        self._store.rewrite_transcript(session_id, messages)
    
    def load_transcript(self, session_id: str) -> list:
        return self._store.load_transcript(session_id)
