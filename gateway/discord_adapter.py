"""
Discord Platform Adapter

Integrates with Discord API for message handling.
Uses Discord's gateway protocol for real-time events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional

import aiohttp
import discord_typings as dt

from .adapter import AdapterConfig, AdapterState, PlatformAdapter
from .message import Message


class DiscordAdapter(PlatformAdapter):
    """
    Discord platform adapter.

    Features:
    - Gateway API connection
    - Slash command support
    - Message components
    - Thread management
    """

    GATEWAY_URL = "wss://gateway.discord.gg"
    API_URL = "https://discord.com/api/v10"

    def __init__(
        self,
        config: DiscordConfig,
        message_handler: Callable[[Message], Coroutine[Any, Any, None]],
    ):
        """
        Initialize Discord adapter.

        Args:
            config: Discord-specific configuration
            message_handler: Async callback for incoming messages
        """
        super().__init__("discord", config, message_handler)
        self.discord_config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[Any] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._gateway_task: Optional[asyncio.Task] = None

        # Gateway state
        self._sequence: Optional[int] = None
        self._session_id: Optional[str] = None
        self._heartbeat_interval: float = 0
        self._gateway_url: str = ""

    @property
    def headers(self) -> dict[str, str]:
        """Get API headers with authentication."""
        return {
            "Authorization": f"Bot {self.discord_config.bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "MimirAether/1.0",
        }

    async def connect(self) -> None:
        """Connect to Discord gateway."""
        self._session = aiohttp.ClientSession()

        # Get gateway URL
        self._gateway_url = await self._get_gateway_url()

        # Start gateway connection
        self._gateway_task = asyncio.create_task(self._gateway_loop())

        self.logger.info("Discord adapter connected")

    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        if self._gateway_task:
            self._gateway_task.cancel()
            try:
                await self._gateway_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._websocket:
            await self._websocket.close()

        if self._session:
            await self._session.close()

        self.logger.info("Discord adapter disconnected")

    async def _get_gateway_url(self) -> str:
        """Get gateway URL from Discord."""
        if not self._session:
            return self.GATEWAY_URL

        url = f"{self.API_URL}/gateway"
        async with self._session.get(url, headers=self.headers) as resp:
            data = await resp.json()
            return data.get("url", self.GATEWAY_URL)

    async def _gateway_loop(self) -> None:
        """Main gateway event loop."""
        import websockets

        while self._state != AdapterState.STOPPING:
            try:
                url = f"{self._gateway_url}?v=10&encoding=json"
                async with websockets.connect(url) as ws:
                    self._websocket = ws

                    # Handle hello
                    hello = await ws.recv()
                    await self._handle_dispatch(hello)

                    # Identify
                    await self._send_identify()

                    # Message loop
                    async for msg in ws:
                        await self._handle_dispatch(msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Gateway error: {e}")
                await asyncio.sleep(self.config.retry_delay)

    async def _handle_dispatch(self, data: Any) -> None:
        """Handle gateway dispatch."""
        try:
            if isinstance(data, str):
                payload = json.loads(data)
            else:
                payload = data

            op = payload.get("op")
            d = payload.get("d", {})

            if op == 10:  # Hello
                self._heartbeat_interval = d.get("heartbeat_interval", 45000) / 1000
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            elif op == 0:  # Dispatch
                self._sequence = d.get("s")
                event = payload.get("t")

                if event == "MESSAGE_CREATE":
                    await self._handle_message_create(d)
                elif event == "MESSAGE_UPDATE":
                    await self._handle_message_update(d)
                elif event == "MESSAGE_DELETE":
                    await self._handle_message_delete(d)
                elif event == "INTERACTION_CREATE":
                    await self._handle_interaction(d)

            elif op == 11:  # Heartbeat ACK
                pass

        except Exception as e:
            self.logger.error(f"Error handling dispatch: {e}")

    async def _send_identify(self) -> None:
        """Send identify payload to gateway."""
        payload = {
            "op": 2,
            "d": {
                "token": self.discord_config.bot_token,
                "properties": {
                    "os": "linux",
                    "browser": "MimirAether",
                    "device": "MimirAether",
                },
                "intents": self.discord_config.intents,
            },
        }
        await self._websocket.send(json.dumps(payload))

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            if self._websocket:
                try:
                    await self._websocket.send(json.dumps({
                        "op": 1,
                        "d": self._sequence,
                    }))
                except Exception as e:
                    self.logger.error(f"Heartbeat error: {e}")
                    break

    async def _handle_message_create(self, data: dict[str, Any]) -> None:
        """Handle new message."""
        # Skip bot messages if configured
        if data.get("author", {}).get("bot") and self.discord_config.skip_bot_messages:
            return

        # Skip system messages
        if data.get("type", 0) != 0:
            return

        raw = {"message": data}
        await self.handle_raw_message(raw)

    async def _handle_message_update(self, data: dict[str, Any]) -> None:
        """Handle message edit."""
        # Could implement edit tracking here
        pass

    async def _handle_message_delete(self, data: dict[str, Any]) -> None:
        """Handle message deletion."""
        # Could implement deletion tracking here
        pass

    async def _handle_interaction(self, data: dict[str, Any]) -> None:
        """Handle Discord interactions (slash commands, buttons, etc.)."""
        interaction_type = data.get("type")

        # Ping
        if interaction_type == 1:
            # Should respond with Pong
            return

        # Application command (slash command)
        if interaction_type == 2:
            raw = {"interaction": data}
            await self.handle_raw_message(raw)

        # Message component (button, select, etc.)
        if interaction_type == 3:
            raw = {"interaction": data}
            await self.handle_raw_message(raw)

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
        Send a message via Discord.

        Args:
            chat_id: Channel ID
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

        url = f"{self.API_URL}/channels/{chat_id}/messages"
        data: dict[str, Any] = {"content": text}

        if reply_to:
            data["message_reference"] = {"message_id": reply_to}

        if media_url:
            data["attachments"] = [{"url": media_url}]

        async with self._session.post(url, json=data, headers=self.headers) as resp:
            if resp.status not in (200, 201):
                text_resp = await resp.text()
                raise RuntimeError(f"Send failed: {resp.status} {text_resp}")

            result = await resp.json()
            return {
                "success": True,
                "platform": "discord",
                "platform_message_id": result["id"],
                "chat_id": chat_id,
            }

    async def _process_raw_message(self, raw: dict[str, Any]) -> Optional[Message]:
        """
        Process raw Discord message to unified format.

        Args:
            raw: Raw Discord message or interaction

        Returns:
            Normalized Message or None
        """
        try:
            return Message.from_platform("discord", raw, {})
        except Exception as e:
            self.logger.error(f"Error processing Discord message: {e}")
            return None

    async def create_interaction_response(
        self,
        interaction_id: str,
        interaction_token: str,
        response_type: int,
        content: str,
    ) -> None:
        """
        Create an interaction response.

        Args:
            interaction_id: Interaction ID
            interaction_token: Interaction token
            response_type: Response type (4=ChannelMessageWithSource)
            content: Message content
        """
        if not self._session:
            return

        url = f"{self.API_URL}/interactions/{interaction_id}/{interaction_token}/callback"
        data = {
            "type": response_type,
            "data": {"content": content},
        }

        async with self._session.post(url, json=data, headers=self.headers) as resp:
            if resp.status not in (200, 204):
                self.logger.error(f"Interaction response failed: {resp.status}")

    async def get_channel(self, channel_id: str) -> dict[str, Any]:
        """Get channel information."""
        if not self._session:
            return {}

        url = f"{self.API_URL}/channels/{channel_id}"
        async with self._session.get(url, headers=self.headers) as resp:
            return await resp.json()


@dataclass
class DiscordConfig(AdapterConfig):
    """Discord-specific configuration."""

    bot_token: str = ""
    intents: int = 1 << 9 | 1 << 15  # GuildMessages | MessageContent
    skip_bot_messages: bool = True
    max_presence: int = 100


from dataclasses import dataclass
