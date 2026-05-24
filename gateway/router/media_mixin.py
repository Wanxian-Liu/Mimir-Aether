"""Gateway router media mixin — extracted from router_mixin (P1-LONG-GOD)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
import time
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from gateway._shared import (
    _check_unavailable_skill,
    _format_gateway_process_notification,
    _load_gateway_config,
    _platform_config_key,
    _resolve_gateway_model,
    _resolve_runtime_agent_kwargs,
    _resolve_hermes_bin,
)
from gateway.home_paths import _hermes_home
from gateway.platforms.base import MessageEvent, MessageType, Platform, merge_pending_message_event
from gateway.restart import _AGENT_PENDING_SENTINEL
from gateway.session import SessionSource, build_session_context, build_session_context_prompt
from utils import atomic_yaml_write

logger = logging.getLogger(__name__)


class MediaMixin:
    """Router media mixin mixin for GatewayRunner."""

    @staticmethod
    def _get_guild_id(event: MessageEvent) -> Optional[int]:
        """Extract Discord guild_id from the raw message object."""
        raw = getattr(event, "raw_message", None)
        if raw is None:
            return None
        # Slash command interaction
        if hasattr(raw, "guild_id") and raw.guild_id:
            return int(raw.guild_id)
        # Regular message
        if hasattr(raw, "guild") and raw.guild:
            return raw.guild.id
        return None

    async def _deliver_media_from_response(
        self,
        response: str,
        event: MessageEvent,
        adapter,
    ) -> None:
        """Extract MEDIA: tags and local file paths from a response and deliver them.

        Called after streaming has already sent the text to the user, so the
        text itself is already delivered — this only handles file attachments
        that the normal _process_message_background path would have caught.
        """
        from pathlib import Path

        try:
            media_files, _ = adapter.extract_media(response)
            _, cleaned = adapter.extract_images(response)
            local_files, _ = adapter.extract_local_files(cleaned)

            _thread_meta = {"thread_id": event.source.thread_id} if event.source.thread_id else None

            _AUDIO_EXTS = {'.ogg', '.opus', '.mp3', '.wav', '.m4a'}
            _VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp'}
            _IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

            for media_path, is_voice in media_files:
                try:
                    ext = Path(media_path).suffix.lower()
                    if ext in _AUDIO_EXTS:
                        await adapter.send_voice(
                            chat_id=event.source.chat_id,
                            audio_path=media_path,
                            metadata=_thread_meta,
                        )
                    elif ext in _VIDEO_EXTS:
                        await adapter.send_video(
                            chat_id=event.source.chat_id,
                            video_path=media_path,
                            metadata=_thread_meta,
                        )
                    elif ext in _IMAGE_EXTS:
                        await adapter.send_image_file(
                            chat_id=event.source.chat_id,
                            image_path=media_path,
                            metadata=_thread_meta,
                        )
                    else:
                        await adapter.send_document(
                            chat_id=event.source.chat_id,
                            file_path=media_path,
                            metadata=_thread_meta,
                        )
                except Exception as e:
                    logger.warning("[%s] Post-stream media delivery failed: %s", adapter.name, e)

            for file_path in local_files:
                try:
                    ext = Path(file_path).suffix.lower()
                    if ext in _IMAGE_EXTS:
                        await adapter.send_image_file(
                            chat_id=event.source.chat_id,
                            image_path=file_path,
                            metadata=_thread_meta,
                        )
                    else:
                        await adapter.send_document(
                            chat_id=event.source.chat_id,
                            file_path=file_path,
                            metadata=_thread_meta,
                        )
                except Exception as e:
                    logger.warning("[%s] Post-stream file delivery failed: %s", adapter.name, e)

        except Exception as e:
            logger.warning("Post-stream media extraction failed: %s", e)
