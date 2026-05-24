"""
MimirAether Gateway - Multi-Platform Message Integration

Phase 5: Multi-Platform Gateway
Supports: Telegram, Discord, Feishu

Architecture:
- BasePlatformAdapter: Abstract base for platform integrations (in platforms/)
- Message: Unified message protocol
- SessionManager: Cross-platform session management
- MessageRouter: Message routing and handling
"""

from .message import Message, MessageType, MessageContext
from .adapter import PlatformAdapter, AdapterConfig
from .message_router import MessageRouter

# SessionManager不存在于session.py，优雅降级
try:
    from .session import SessionManager, Session
except ImportError:
    SessionManager = None
    Session = None

# 可选适配器 - 从platforms子目录导入，失败时优雅降级
try:
    from .platforms.telegram_adapter import TelegramAdapter
except ImportError:
    TelegramAdapter = None

try:
    from .platforms.discord_adapter import DiscordAdapter
except ImportError:
    DiscordAdapter = None

try:
    from .platforms.feishu_adapter import FeishuAdapter
except ImportError:
    FeishuAdapter = None

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
