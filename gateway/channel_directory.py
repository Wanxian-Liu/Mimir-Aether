"""
Channel directory — maps channel/platform identifiers to adapter instances.

# TODO-自研: 渠道目录注册表，可扩展支持自定义渠道
"""

from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ChannelDirectory:
    """Maps channel identifiers to their adapter instances.

    # TODO-自研: 可扩展为动态注册机制，支持运行时添加/移除渠道
    """

    def __init__(self):
        self._channels: Dict[str, Any] = {}

    def register(self, channel_id: str, adapter: Any) -> None:
        """Register an adapter for a given channel.

        # TODO-自研: 可增加优先级、权重等配置
        """
        self._channels[channel_id] = adapter
        logger.debug("Registered channel: %s", channel_id)

    def get(self, channel_id: str) -> Optional[Any]:
        """Get the adapter for a channel, or None if not registered."""
        return self._channels.get(channel_id)

    def unregister(self, channel_id: str) -> None:
        """Remove a channel from the directory."""
        if channel_id in self._channels:
            del self._channels[channel_id]
            logger.debug("Unregistered channel: %s", channel_id)

    def list_channels(self) -> list[str]:
        """List all registered channel IDs."""
        return list(self._channels.keys())

    def clear(self) -> None:
        """Clear all registered channels."""
        self._channels.clear()
