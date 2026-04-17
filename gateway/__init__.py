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

# 可选适配器 - 导入失败时优雅降级
try:
    from .telegram_adapter import TelegramAdapter
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
    ]
except ImportError:
    TelegramAdapter = None
    __all__ = [
        "Message",
        "MessageType",
        "MessageContext",
        "PlatformAdapter",
        "AdapterConfig",
        "SessionManager",
        "Session",
        "MessageRouter",
    ]

try:
    from .discord_adapter import DiscordAdapter
    __all__.append("DiscordAdapter")
except ImportError:
    DiscordAdapter = None

try:
    from .feishu_adapter import FeishuAdapter
    __all__.append("FeishuAdapter")
except ImportError:
    FeishuAdapter = None
