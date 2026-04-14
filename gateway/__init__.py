"""
MimirAether Gateway - Multi-Platform Message Integration

Phase 5: Multi-Platform Gateway
Supports: Telegram, Discord, Feishu

Architecture:
- PlatformAdapter: Abstract base for platform integrations
- Message: Unified message protocol
- SessionManager: Cross-platform session management
- MessageRouter: Message routing and handling
"""

from .message import Message, MessageType, MessageContext
from .adapter import PlatformAdapter, AdapterConfig
from .session import SessionManager, Session
from .router import MessageRouter
from .telegram_adapter import TelegramAdapter
from .discord_adapter import DiscordAdapter
from .feishu_adapter import FeishuAdapter

__all__ = [
    "Message",
    "MessageType",
    "MessageContext",
    "PlatformAdapter",
    "AdapterConfig",
    "SessionManager",
    "Session",
    "MessageRouter",
    "TelegramAdapter",
    "DiscordAdapter",
    "FeishuAdapter",
]
