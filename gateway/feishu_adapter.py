"""
Feishu (Lark) Platform Adapter

Integrates with Feishu Open Platform for message handling.
Supports webhook verification and callback handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any, Callable, Coroutine, Optional

import aiohttp

from .adapter import AdapterConfig, AdapterState, PlatformAdapter
from .message import Message


class FeishuAdapter(PlatformAdapter):
    """
    Feishu (Lark) platform adapter.

    Features:
    - Webhook event handling
    - Outgoing webhook support
    - Card messages
    - Multi-tenant support
    """

    API_URL = "https://open.feishu.cn/open-apis"
    WEBHOOK_VERIFY_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

    def __init__(
        self,
        config: FeishuConfig,
        message_handler: Callable[[Message], Coroutine[Any, Any, None]],
    ):
        """
        Initialize Feishu adapter.

        Args:
            config: Feishu-specific configuration
            message_handler: Async callback for incoming messages
        """
        super().__init__("feishu", config, message_handler)
        self.feishu_config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._tenant_token: Optional[str] = None
        self._token_expires_at: float = 0

    @property
    def headers(self) -> dict[str, str]:
        """Get API headers with authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        if self._tenant_token and time.time() < self._token_expires_at:
            headers["Authorization"] = f"Bearer {self._tenant_token}"
        return headers

    async def connect(self) -> None:
        """Connect to Feishu."""
        self._session = aiohttp.ClientSession()

        # Get tenant access token
        await self._refresh_token()

        self.logger.info("Feishu adapter connected")

    async def disconnect(self) -> None:
        """Disconnect from Feishu."""
        if self._session:
            await self._session.close()

        self.logger.info("Feishu adapter disconnected")

    async def _refresh_token(self) -> None:
        """Refresh tenant access token."""
        if not self._session:
            return

        url = self.WEBHOOK_VERIFY_URL
        data = {
            "app_id": self.feishu_config.app_id,
            "app_secret": self.feishu_config.app_secret,
        }

        async with self._session.post(url, json=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                if result.get("code") == 0:
                    self._tenant_token = result.get("tenant_access_token")
                    # Token typically expires in 2 hours
                    self._token_expires_at = time.time() + 7000
                    self.logger.debug("Feishu token refreshed")
                else:
                    self.logger.error(f"Token refresh failed: {result}")
            else:
                self.logger.error(f"Token request failed: {resp.status}")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        thread_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        media_url: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Send a message via Feishu.

        Args:
            chat_id: Chat ID (open_id for users, chat_id for groups)
            text: Message text
            thread_id: Thread ID (optional)
            reply_to: Message ID to reply to
            media_url: Media URL
            **kwargs: Additional parameters

        Returns:
            Response with success status and message info
        """
        if not self._session:
            raise RuntimeError("Not connected")

        # Ensure token is valid
        if time.time() >= self._token_expires_at - 60:
            await self._refresh_token()

        url = f"{self.API_URL}/im/v1/messages"
        params = {
            "receive_id_type": "open_id",
        }

        # Prepare content
        content: dict[str, Any] = {"text": text}

        data = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps(content),
        }

        if reply_to:
            data["reply_to_message_id"] = reply_to

        if thread_id:
            data["thread_id"] = thread_id

        async with self._session.post(
            url,
            json=data,
            params=params,
            headers=self.headers,
        ) as resp:
            result = await resp.json()
            if result.get("code") != 0:
                raise RuntimeError(f"Send failed: {result}")

            return {
                "success": True,
                "platform": "feishu",
                "platform_message_id": result.get("data", {}).get("message_id", ""),
                "chat_id": chat_id,
            }

    async def send_card(
        self,
        chat_id: str,
        card_content: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Send a card message via Feishu.

        Args:
            chat_id: Chat ID
            card_content: Card element content
            **kwargs: Additional parameters

        Returns:
            Response with success status
        """
        if not self._session:
            raise RuntimeError("Not connected")

        if time.time() >= self._token_expires_at - 60:
            await self._refresh_token()

        url = f"{self.API_URL}/im/v1/messages"
        params = {
            "receive_id_type": "open_id",
        }

        data = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content),
        }

        async with self._session.post(
            url,
            json=data,
            params=params,
            headers=self.headers,
        ) as resp:
            result = await resp.json()
            if result.get("code") != 0:
                raise RuntimeError(f"Card send failed: {result}")

            return {
                "success": True,
                "platform": "feishu",
                "platform_message_id": result.get("data", {}).get("message_id", ""),
                "chat_id": chat_id,
            }

    async def handle_webhook(self, payload: dict[str, Any], headers: Optional[dict] = None) -> None:
        """
        Handle incoming webhook event from Feishu.

        Args:
            payload: Webhook payload
            headers: Request headers for verification
        """
        # Verify webhook if configured
        if self.feishu_config.verification_token:
            challenge = payload.get("challenge")
            if challenge:
                # This is a URL verification request
                return

        event_type = payload.get("header", {}).get("event_type")

        # Handle different event types
        if event_type == "im.message.receive_v1":
            await self._handle_message_receive(payload)
        elif event_type == "im.message.direct_mention_v1":
            await self._handle_mention(payload)

    async def _handle_message_receive(self, payload: dict[str, Any]) -> None:
        """Handle received message event."""
        raw = {
            "message": payload.get("event", {}).get("message", {}),
            "sender": payload.get("event", {}).get("sender", {}),
            "chat_id": payload.get("event", {}).get("chat_id"),
            "chat_type": payload.get("event", {}).get("chat_type"),
        }
        await self.handle_raw_message(raw)

    async def _handle_mention(self, payload: dict[str, Any]) -> None:
        """Handle direct mention event."""
        raw = {
            "message": payload.get("event", {}).get("message", {}),
            "sender": payload.get("event", {}).get("sender", {}),
            "chat_id": payload.get("event", {}).get("chat_id"),
            "chat_type": payload.get("event", {}).get("chat_type"),
        }
        await self.handle_raw_message(raw)

    async def _process_raw_message(self, raw: dict[str, Any]) -> Optional[Message]:
        """
        Process raw Feishu message to unified format.

        Args:
            raw: Raw Feishu message

        Returns:
            Normalized Message or None
        """
        try:
            return Message.from_platform("feishu", raw, {})
        except Exception as e:
            self.logger.error(f"Error processing Feishu message: {e}")
            return None

    def verify_webhook(self, payload: bytes, signature: Optional[str] = None) -> bool:
        """
        Verify Feishu webhook signature.

        Args:
            payload: Raw request body
            signature: X-Lark-Signature header

        Returns:
            True if signature is valid
        """
        if not self.feishu_config.encrypt_key:
            return True

        if not signature:
            return False

        expected = hmac.new(
            self.feishu_config.encrypt_key.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def get_user_info(self, open_id: str) -> dict[str, Any]:
        """
        Get user information by open_id.

        Args:
            open_id: User's open_id

        Returns:
            User information dict
        """
        if not self._session:
            return {}

        url = f"{self.API_URL}/contact/v3/users/{open_id}"
        params = {"user_id_type": "open_id"}

        async with self._session.get(
            url,
            params=params,
            headers=self.headers,
        ) as resp:
            return await resp.json()

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """
        Get chat information.

        Args:
            chat_id: Chat ID

        Returns:
            Chat information dict
        """
        if not self._session:
            return {}

        url = f"{self.API_URL}/im/v1/chats/{chat_id}"

        async with self._session.get(url, headers=self.headers) as resp:
            return await resp.json()


@dataclass
class FeishuConfig(AdapterConfig):
    """Feishu-specific configuration."""

    app_id: str = ""
    app_secret: str = ""
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None
    bot_name: Optional[str] = None


import json
from dataclasses import dataclass
