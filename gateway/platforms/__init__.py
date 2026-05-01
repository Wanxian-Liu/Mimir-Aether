"""
Gateway Platform Adapters

This package contains platform-specific adapters for various messaging platforms.
Each adapter inherits from BasePlatformAdapter and implements the required methods.
"""

from .base import BasePlatformAdapter

# Import available platform adapters
_import_errors = {}

try:
    from .telegram_adapter import TelegramAdapter
except ImportError as e:
    TelegramAdapter = None
    _import_errors["telegram"] = str(e)

try:
    from .discord_adapter import DiscordAdapter
except ImportError as e:
    DiscordAdapter = None
    _import_errors["discord"] = str(e)

try:
    from .feishu_adapter import FeishuAdapter
except ImportError as e:
    FeishuAdapter = None
    _import_errors["feishu"] = str(e)

try:
    from .whatsapp import WhatsAppAdapter
except ImportError as e:
    WhatsAppAdapter = None
    _import_errors["whatsapp"] = str(e)

try:
    from .homeassistant import HomeAssistantAdapter
except ImportError as e:
    HomeAssistantAdapter = None
    _import_errors["homeassistant"] = str(e)


def get_adapter(name: str):
    """Get a platform adapter by name."""
    adapters = {
        "telegram": TelegramAdapter,
        "discord": DiscordAdapter,
        "feishu": FeishuAdapter,
        "lark": FeishuAdapter,  # Alias
        "whatsapp": WhatsAppAdapter,
        "homeassistant": HomeAssistantAdapter,
        "home_assistant": HomeAssistantAdapter,  # Alias
        "ha": HomeAssistantAdapter,  # Alias
    }
    adapter = adapters.get(name.lower())
    if adapter is None:
        raise ValueError(f"Unknown platform adapter: {name}")
    if adapter is None and name.lower() in _import_errors:
        raise ImportError(f"Failed to import {name} adapter: {_import_errors[name.lower()]}")
    return adapter


__all__ = [
    "BasePlatformAdapter",
    "TelegramAdapter",
    "DiscordAdapter",
    "FeishuAdapter",
    "WhatsAppAdapter",
    "HomeAssistantAdapter",
    "get_adapter",
]
