"""
Unified Message Protocol for MimirAether Gateway

Provides a consistent message format across all supported platforms:
- Telegram
- Discord
- Feishu
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MessageType(Enum):
    """Message type classification."""

    TEXT = "text"
    MEDIA = "media"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    COMMAND = "command"
    CALLBACK = "callback"
    SYSTEM = "system"


class ChatType(Enum):
    """Chat type classification."""

    DIRECT = "direct"
    GROUP = "group"
    CHANNEL = "channel"
    THREAD = "thread"


@dataclass
class MessageContext:
    """Platform-specific context for a message."""

    platform: str
    platform_message_id: str
    chat_id: str
    chat_type: ChatType
    sender_id: str
    sender_name: str
    sender_username: Optional[str] = None
    thread_id: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    is_bot: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """
    Unified message format for all platforms.

    This is the core protocol that normalizes messages from different
    platforms into a consistent structure.
    """

    # Core fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.TEXT
    text: str = ""

    # Metadata
    context: Optional[MessageContext] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Content fields
    media_url: Optional[str] = None
    media_caption: Optional[str] = None
    media_file_id: Optional[str] = None

    # Command fields
    command: Optional[str] = None
    command_args: list[str] = field(default_factory=list)

    # Callback fields
    callback_data: Optional[str] = None
    callback_message_id: Optional[str] = None

    # Session linkage
    session_id: Optional[str] = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_platform(
        cls,
        platform: str,
        raw_message: dict[str, Any],
        config: dict[str, Any],
    ) -> Message:
        """
        Factory method to create a Message from platform-specific raw data.

        Args:
            platform: Platform identifier (telegram, discord, feishu)
            raw_message: Raw message dict from platform SDK
            config: Platform adapter configuration

        Returns:
            Normalized Message instance
        """
        normalizers = {
            "telegram": cls._normalize_telegram,
            "discord": cls._normalize_discord,
            "feishu": cls._normalize_feishu,
        }

        normalizer = normalizers.get(platform.lower())
        if not normalizer:
            raise ValueError(f"Unknown platform: {platform}")

        return normalizer(raw_message, config)

    @classmethod
    def _normalize_telegram(
        cls,
        raw: dict[str, Any],
        config: dict[str, Any],
    ) -> Message:
        """Normalize Telegram message to unified format."""
        message = raw.get("message", raw)
        chat = message.get("chat", {})
        from_user = message.get("from", {})

        # Determine message type
        msg_type = MessageType.TEXT
        if message.get("sticker"):
            msg_type = MessageType.STICKER
        elif message.get("photo"):
            msg_type = MessageType.MEDIA
        elif message.get("audio"):
            msg_type = MessageType.AUDIO
        elif message.get("video"):
            msg_type = MessageType.VIDEO
        elif message.get("document"):
            msg_type = MessageType.DOCUMENT
        elif message.get("location"):
            msg_type = MessageType.LOCATION
        elif message.get("contact"):
            msg_type = MessageType.CONTACT
        elif message.get("entities"):
            # Check for bot commands
            for entity in message["entities"]:
                if entity.get("type") == "bot_command":
                    msg_type = MessageType.COMMAND
                    break

        # Extract text
        text = message.get("text", message.get("caption", ""))

        # Extract command
        command = None
        command_args: list[str] = []
        if msg_type == MessageType.COMMAND and text:
            parts = text.split()
            if parts:
                command = parts[0].lstrip("/")
                command_args = parts[1:]

        # Handle callback query
        callback_data = None
        callback_message_id = None
        if raw.get("callback_query"):
            callback_data = raw["callback_query"].get("data")
            callback_message_id = str(raw["callback_query"].get("message", {}).get("message_id", ""))

        context = MessageContext(
            platform="telegram",
            platform_message_id=str(message.get("message_id", "")),
            chat_id=str(chat.get("id", "")),
            chat_type=ChatType.GROUP if chat.get("type") == "group" else ChatType.DIRECT,
            sender_id=str(from_user.get("id", "")),
            sender_name=f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
            sender_username=from_user.get("username"),
            thread_id=str(message.get("message_thread_id")) if message.get("message_thread_id") else None,
            reply_to_message_id=str(message.get("reply_to_message", {}).get("message_id")) if message.get("reply_to_message") else None,
            is_bot=from_user.get("is_bot", False),
            raw=raw,
        )

        return cls(
            type=msg_type,
            text=text,
            context=context,
            media_url=cls._extract_telegram_media(message),
            command=command,
            command_args=command_args,
            callback_data=callback_data,
            callback_message_id=callback_message_id,
        )

    @classmethod
    def _normalize_discord(
        cls,
        raw: dict[str, Any],
        config: dict[str, Any],
    ) -> Message:
        """Normalize Discord message to unified format."""
        author = raw.get("author", {})
        channel = raw.get("channel", {})
        guild = raw.get("guild", {})

        # Determine message type
        msg_type = MessageType.TEXT
        attachments = raw.get("attachments", [])
        if attachments:
            att = attachments[0]
            if att.get("content_type", "").startswith("image/"):
                msg_type = MessageType.MEDIA
            elif att.get("content_type", "").startswith("audio/"):
                msg_type = MessageType.AUDIO
            elif att.get("content_type", "").startswith("video/"):
                msg_type = MessageType.VIDEO
            else:
                msg_type = MessageType.DOCUMENT

        if raw.get("sticker"):
            msg_type = MessageType.STICKER

        # Check for mentions that might be commands
        content = raw.get("content", "")
        if content.startswith("/") or content.startswith("!"):
            msg_type = MessageType.COMMAND

        # Extract command
        command = None
        command_args: list[str] = []
        if msg_type == MessageType.COMMAND and content:
            parts = content.split()
            if parts:
                command = parts[0].lstrip("/!")
                command_args = parts[1:]

        context = MessageContext(
            platform="discord",
            platform_message_id=str(raw.get("id", "")),
            chat_id=str(channel.get("id", "")),
            chat_type=ChatType.GROUP if guild else ChatType.DIRECT,
            sender_id=str(author.get("id", "")),
            sender_name=author.get("username", ""),
            sender_username=author.get("username"),
            thread_id=str(raw.get("thread", {}).get("id")) if raw.get("thread") else None,
            reply_to_message_id=str(raw.get("referenced_message", {}).get("id")) if raw.get("referenced_message") else None,
            is_bot=author.get("bot", False),
            raw=raw,
        )

        return cls(
            type=msg_type,
            text=content,
            context=context,
            media_url=attachments[0].get("url") if attachments else None,
            command=command,
            command_args=command_args,
        )

    @classmethod
    def _normalize_feishu(
        cls,
        raw: dict[str, Any],
        config: dict[str, Any],
    ) -> Message:
        """Normalize Feishu message to unified format."""
        msg = raw.get("message", {})
        sender = raw.get("sender", {})
        chat = raw.get("chat_id", {})

        # Determine message type
        msg_type = MessageType.TEXT
        msg_content = msg.get("content", "{}")
        try:
            content = json.loads(msg_content) if isinstance(msg_content, str) else msg_content
        except (json.JSONDecodeError, TypeError):
            content = {}

        content_type = msg.get("msg_type", "text")
        if content_type == "text":
            msg_type = MessageType.TEXT
        elif content_type == "image":
            msg_type = MessageType.MEDIA
        elif content_type == "audio":
            msg_type = MessageType.AUDIO
        elif content_type == "video":
            msg_type = MessageType.VIDEO
        elif content_type == "file":
            msg_type = MessageType.DOCUMENT
        elif content_type == "location":
            msg_type = MessageType.LOCATION

        # Extract text
        text = content.get("text", "") if isinstance(content, dict) else ""

        # Check for commands
        if text.startswith("/"):
            msg_type = MessageType.COMMAND
            parts = text.split()
            command = parts[0].lstrip("/") if parts else None
            command_args = parts[1:] if len(parts) > 1 else []
        else:
            command = None
            command_args = []

        context = MessageContext(
            platform="feishu",
            platform_message_id=str(msg.get("message_id", "")),
            chat_id=str(chat) if isinstance(chat, str) else str(chat.get("chat_id", "")),
            chat_type=ChatType.GROUP if raw.get("chat_type") == "group" else ChatType.DIRECT,
            sender_id=str(sender.get("id", "")),
            sender_name=sender.get("name", sender.get("id", "")),
            sender_username=sender.get("username"),
            thread_id=msg.get("thread_id"),
            reply_to_message_id=msg.get("reply_to_message_id"),
            is_bot=sender.get("sender_type") == "bot",
            raw=raw,
        )

        return cls(
            type=msg_type,
            text=text,
            context=context,
            media_url=content.get("image_key") if msg_type == MessageType.MEDIA else None,
            command=command,
            command_args=command_args,
        )

    @staticmethod
    def _extract_telegram_media(message: dict[str, Any]) -> Optional[str]:
        """Extract media URL from Telegram message."""
        if message.get("photo"):
            # Get largest photo
            photos = sorted(message["photo"], key=lambda x: x.get("file_size", 0), reverse=True)
            return photos[0].get("file_id") if photos else None
        elif message.get("audio"):
            return message["audio"].get("file_id")
        elif message.get("video"):
            return message["video"].get("file_id")
        elif message.get("document"):
            return message["document"].get("file_id")
        return None

    def to_outbound(self) -> dict[str, Any]:
        """
        Convert Message to platform-specific outbound format.

        Returns:
            Dict with platform-specific fields for sending
        """
        if not self.context:
            raise ValueError("Message has no context")

        return {
            "platform": self.context.platform,
            "chat_id": self.context.chat_id,
            "text": self.text,
            "thread_id": self.context.thread_id,
            "reply_to_message_id": self.context.reply_to_message_id,
            "media_url": self.media_url,
        }


import json
