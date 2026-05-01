"""
Mirror module — mirrors/syncs messages across multiple channels.

# 可扩展: 跨渠道消息镜像
"""

import logging
from typing import Optional, Any, List

logger = logging.getLogger(__name__)


class MirrorMessage:
    """Represents a message to be mirrored to multiple channels.

    # 可扩展: 消息转换/格式化/过滤
    """

    def __init__(
        self,
        content: str,
        source_channel: str,
        source_message_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.content = content
        self.source_channel = source_channel
        self.source_message_id = source_message_id
        self.metadata = metadata or {}


class ChannelMirror:
    """Mirrors/syncs messages across multiple channels.

    # 可扩展: 消息同步策略
    """

    def __init__(self, channel_directory: Any):
        self.channel_directory = channel_directory

    async def mirror_message(
        self,
        message: MirrorMessage,
        target_channels: Optional[List[str]] = None,
    ) -> dict[str, bool]:
        """Mirror a message to target channels.

        # 可扩展: 消息队列/重试/并发控制
        """
        results = {}
        if target_channels is None:
            target_channels = [
                ch for ch in self.channel_directory.list_channels()
                if ch != message.source_channel
            ]

        for channel_id in target_channels:
            adapter = self.channel_directory.get(channel_id)
            if not adapter:
                logger.warning("No adapter for channel: %s", channel_id)
                results[channel_id] = False
                continue

            try:
                result = await adapter.send(
                    chat_id=getattr(message.metadata, "chat_id", channel_id),
                    content=message.content,
                    metadata=message.metadata,
                )
                results[channel_id] = result.success
            except Exception as e:
                logger.error("Mirror error for %s: %s", channel_id, e)
                results[channel_id] = False

        return results

    async def mirror_media(
        self,
        media_path: str,
        caption: Optional[str] = None,
        source_channel: Optional[str] = None,
        target_channels: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> dict[str, bool]:
        """Mirror a media file to target channels.

        # 可扩展: 媒体文件镜像分发
        """
        results = {}
        if target_channels is None:
            target_channels = [
                ch for ch in self.channel_directory.list_channels()
                if ch != source_channel
            ]

        for channel_id in target_channels:
            adapter = self.channel_directory.get(channel_id)
            if not adapter:
                results[channel_id] = False
                continue

            try:
                result = await adapter.send_media(
                    chat_id=getattr(metadata, "chat_id", channel_id) if metadata else channel_id,
                    media_path=media_path,
                    caption=caption,
                    metadata=metadata or {},
                )
                results[channel_id] = getattr(result, "success", False)
            except Exception as e:
                logger.error("Media mirror error for %s: %s", channel_id, e)
                results[channel_id] = False

        return results
