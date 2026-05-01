"""
Shared platform registry for MimirAether.

Single source of truth for platform metadata consumed by both
skills_config (label display) and tools_config (default toolset
resolution).  Import ``PLATFORMS`` from here instead of maintaining
duplicate dicts in each module.
"""

from collections import OrderedDict
from typing import NamedTuple


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="mimir-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="mimir-telegram")),
    ("discord",        PlatformInfo(label="💬 Discord",         default_toolset="mimir-discord")),
    ("slack",          PlatformInfo(label="💼 Slack",           default_toolset="mimir-slack")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="mimir-whatsapp")),
    ("signal",         PlatformInfo(label="📡 Signal",          default_toolset="mimir-signal")),
    ("bluebubbles",    PlatformInfo(label="💙 BlueBubbles",     default_toolset="mimir-bluebubbles")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="mimir-email")),
    ("homeassistant",  PlatformInfo(label="🏠 Home Assistant",  default_toolset="mimir-homeassistant")),
    ("mattermost",     PlatformInfo(label="💬 Mattermost",      default_toolset="mimir-mattermost")),
    ("matrix",         PlatformInfo(label="💬 Matrix",          default_toolset="mimir-matrix")),
    ("dingtalk",       PlatformInfo(label="💬 DingTalk",        default_toolset="mimir-dingtalk")),
    ("feishu",         PlatformInfo(label="🪽 Feishu",          default_toolset="mimir-feishu")),
    ("wecom",          PlatformInfo(label="💬 WeCom",           default_toolset="mimir-wecom")),
    ("wecom_callback", PlatformInfo(label="💬 WeCom Callback",  default_toolset="mimir-wecom-callback")),
    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="mimir-weixin")),
    ("webhook",        PlatformInfo(label="🔗 Webhook",         default_toolset="mimir-webhook")),
    ("api_server",     PlatformInfo(label="🌐 API Server",      default_toolset="mimir-api-server")),
])


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key, or *default*."""
    info = PLATFORMS.get(key)
    return info.label if info is not None else default
