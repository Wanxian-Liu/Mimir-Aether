"""
Telegram Platform Adapter

Integrates with Telegram Bot API for message handling.
Supports both polling and webhook modes.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

import aiohttp

from ..adapter import AdapterConfig, AdapterState, AdapterStatus, PlatformAdapter
from ..message import Message


class TelegramAdapter(PlatformAdapter):
    """
    Telegram platform adapter.

    Features:
    - Polling mode for development
    - Webhook mode for production
    - Bot command handling
    - Inline query support
    - Callback query handling
    """

    API_BASE = "https://api.telegram.org"

    def __init__(
        self,
        config: TelegramConfig,
        message_handler: Callable[[Message], Coroutine[Any, Any, None]],
    ):
        """
        Initialize Telegram adapter.

        Args:
            config: Telegram-specific configuration
            message_handler: Async callback for incoming messages
        """
        super().__init__("telegram", config, message_handler)
        self.telegram_config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._offset = 0

    @property
    def api_url(self) -> str:
        """Get the API URL for this bot."""
        return f"{self.API_BASE}/bot{self.telegram_config.bot_token}"

    async def connect(self) -> None:
        """Connect to Telegram."""
        self._session = aiohttp.ClientSession()

        if self.telegram_config.use_webhook:
            await self._setup_webhook()
        else:
            self._polling_task = asyncio.create_task(self._polling_loop())

        self.logger.info("Telegram adapter connected")

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        if self._session:
            await self._session.close()

        self.logger.info("Telegram adapter disconnected")

    async def _polling_loop(self) -> None:
        """Poll Telegram for updates."""
        while self._state != AdapterState.STOPPING:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self.handle_raw_message(update)

                if updates:
                    # Update offset to acknowledge processed updates
                    last_update_id = max(int(u.get("update_id", 0)) for u in updates)
                    self._offset = last_update_id + 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
                await asyncio.sleep(self.config.retry_delay)

    async def _get_updates(self) -> list[dict[str, Any]]:
        """Fetch updates from Telegram."""
        if not self._session:
            return []

        url = f"{self.api_url}/getUpdates"
        params = {
            "offset": self._offset,
            "timeout": self.telegram_config.poll_timeout,
            "allowed_updates": json.dumps(self.telegram_config.allowed_updates),
        }

        async with self._session.get(url, params=params) as resp:
            if resp.status != 200:
                self.logger.error(f"API error: {resp.status}")
                return []

            data = await resp.json()
            if not data.get("ok"):
                self.logger.error(f"API returned error: {data}")
                return []

            return data.get("result", [])

    async def _setup_webhook(self) -> None:
        """Set up webhook for Telegram."""
        if not self._session:
            return

        # Delete existing webhook first
        url = f"{self.api_url}/deleteWebhook"
        await self._session.post(url)

        # Set new webhook
        webhook_url = f"{self.telegram_config.webhook_url}{self.config.webhook_path}"
        url = f"{self.api_url}/setWebhook"
        params = {
            "url": webhook_url,
            "secret_token": self.config.webhook_secret,
            "certificate": self.telegram_config.certificate,
        }

        async with self._session.post(url, json=params) as resp:
            data = await resp.json()
            if not data.get("ok"):
                self.logger.error(f"Failed to set webhook: {data}")
                raise RuntimeError(f"Webhook setup failed: {data}")

        self.logger.info(f"Webhook set to {webhook_url}")

    async def handle_webhook(self, payload: dict[str, Any], secret: Optional[str] = None) -> None:
        """
        Handle incoming webhook request.

        Args:
            payload: Webhook payload
            secret: Secret token for verification
        """
        # Verify secret if configured
        if self.config.webhook_secret and secret != self.config.webhook_secret:
            self.logger.warning("Invalid webhook secret")
            return

        await self.handle_raw_message(payload)

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
        Send a message via Telegram.

        Args:
            chat_id: Target chat ID
            text: Message text
            thread_id: Message thread ID (for supergroups)
            reply_to: Message ID to reply to
            media_url: Media URL for media messages
            **kwargs: Additional parameters

        Returns:
            Response with success status and message info
        """
        if not self._session:
            raise RuntimeError("Not connected")

        url = f"{self.api_url}/sendMessage"
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }

        if thread_id:
            data["message_thread_id"] = int(thread_id)
        if reply_to:
            data["reply_to_message_id"] = int(reply_to)
        if kwargs.get("parse_mode"):
            data["parse_mode"] = kwargs["parse_mode"]
        if kwargs.get("disable_web_page_preview"):
            data["disable_web_page_preview"] = True
        if kwargs.get("disable_notification"):
            data["disable_notification"] = True

        # Handle media
        if media_url:
            if media_url.startswith("http"):
                # Send as photo
                data["photo"] = media_url
            else:
                # Send as file_id
                data["photo"] = media_url

        async with self._session.post(url, json=data) as resp:
            result = await resp.json()
            if not result.get("ok"):
                raise RuntimeError(f"Send failed: {result}")

            return {
                "success": True,
                "platform": "telegram",
                "platform_message_id": str(result["result"]["message_id"]),
                "chat_id": chat_id,
            }

    async def _process_raw_message(self, raw: dict[str, Any]) -> Optional[Message]:
        """
        Process raw Telegram update to unified Message format.

        Args:
            raw: Raw Telegram update

        Returns:
            Normalized Message or None
        """
        try:
            return Message.from_platform("telegram", raw, {})
        except Exception as e:
            self.logger.error(f"Error processing Telegram message: {e}")
            return None

    async def get_me(self) -> dict[str, Any]:
        """Get bot information."""
        if not self._session:
            return {}

        url = f"{self.api_url}/getMe"
        async with self._session.get(url) as resp:
            return await resp.json()

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """Get file download URL."""
        if not self._session:
            return {}

        url = f"{self.api_url}/getFile"
        async with self._session.post(url, json={"file_id": file_id}) as resp:
            return await resp.json()

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Telegram webhook signature.

        Args:
            payload: Raw request body
            signature: X-Telegram-Webhook-Signature header

        Returns:
            True if signature is valid
        """
        if not self.config.webhook_secret:
            return True

        expected = hmac.new(
            self.config.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)


@dataclass
class TelegramConfig(AdapterConfig):
    """Telegram-specific configuration."""

    bot_token: str = ""
    use_webhook: bool = False
    webhook_url: str = ""
    certificate: Optional[dict] = None
    poll_timeout: int = 55
    allowed_updates: list[str] = field(
        default_factory=lambda: ["message", "edited_message", "callback_query"],
    )


from dataclasses import dataclass, field
