"""
Delivery module — handles message/media delivery after agent response.

# TODO-自研: 消息投递与媒体分发，可扩展支持更多投递策略
"""

import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)


class DeliveryResult:
    """Result of a delivery operation."""

    def __init__(self, success: bool, error: Optional[str] = None, message_id: Optional[str] = None):
        self.success = success
        self.error = error
        self.message_id = message_id


class MessageDelivery:
    """Handles delivery of final messages and media attachments.

    # TODO-自研: 可扩展为投递队列、重试机制、优先级调度
    """

    def __init__(self, adapter: Any):
        self.adapter = adapter

    async def deliver_message(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> DeliveryResult:
        """Deliver a final text message.

        # TODO-自研: 可增加消息队列、批量投递、延迟投递等功能
        """
        try:
            result = await self.adapter.send(
                chat_id=chat_id,
                content=content,
                reply_to=reply_to,
                metadata=metadata or {},
            )
            return DeliveryResult(
                success=result.success,
                error=getattr(result, "error", None),
                message_id=getattr(result, "message_id", None),
            )
        except Exception as e:
            logger.error("Delivery error: %s", e)
            return DeliveryResult(success=False, error=str(e))

    async def deliver_media(
        self,
        chat_id: str,
        media_paths: List[str],
        caption: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> List[DeliveryResult]:
        """Deliver media files.

        # TODO-自研: 媒体文件分发，支持多种媒体类型、批量上传
        """
        results = []
        for path in media_paths:
            try:
                result = await self.adapter.send_media(
                    chat_id=chat_id,
                    media_path=path,
                    caption=caption,
                    metadata=metadata or {},
                )
                results.append(DeliveryResult(
                    success=getattr(result, "success", False),
                    error=getattr(result, "error", None),
                    message_id=getattr(result, "message_id", None),
                ))
            except Exception as e:
                logger.error("Media delivery error for %s: %s", path, e)
                results.append(DeliveryResult(success=False, error=str(e)))
        return results
