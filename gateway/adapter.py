"""
PlatformAdapter - Abstract Base for Multi-Platform Integration

Each supported platform (Telegram, Discord, Feishu) implements this interface.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from .message import Message


class AdapterState(Enum):
    """Platform adapter lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class AdapterConfig:
    """Base configuration for platform adapters."""

    enabled: bool = True
    polling_interval: float = 1.0
    max_retries: int = 3
    retry_delay: float = 5.0
    webhook_secret: Optional[str] = None
    webhook_path: str = "/webhook"
    rate_limit_messages: int = 30
    rate_limit_period: float = 60.0


@dataclass
class AdapterStatus:
    """Runtime status of a platform adapter."""

    state: AdapterState = AdapterState.STOPPED
    last_start_at: Optional[datetime] = None
    last_stop_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_message_at: Optional[datetime] = None
    messages_processed: int = 0
    errors_count: int = 0


class PlatformAdapter(ABC):
    """
    Abstract base class for platform adapters.

    Each platform (Telegram, Discord, Feishu) must implement:
    - connect: Establish connection to the platform
    - disconnect: Close connection gracefully
    - send_message: Send a message to the platform
    - _process_raw_message: Convert platform-specific message to unified Message
    """

    def __init__(
        self,
        name: str,
        config: AdapterConfig,
        message_handler: Callable[[Message], Coroutine[Any, Any, None]],
    ):
        """
        Initialize platform adapter.

        Args:
            name: Platform name (telegram, discord, feishu)
            config: Adapter configuration
            message_handler: Async callback for incoming messages
        """
        self.name = name
        self.config = config
        self.message_handler = message_handler
        self.logger = logging.getLogger(f"gateway.{name}")
        self.status = AdapterStatus()

        self._state = AdapterState.STOPPED
        self._abort_event: Optional[asyncio.Event] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> AdapterState:
        """Get current adapter state."""
        return self._state

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the platform.

        This method should:
        - Validate configuration
        - Set up webhook endpoints or start polling
        - Update state to RUNNING on success
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Gracefully close connection to the platform.

        This method should:
        - Stop polling or webhooks
        - Clean up resources
        - Update state to STOPPED
        """
        pass

    @abstractmethod
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
        Send a message to the platform.

        Args:
            chat_id: Target chat/channel ID
            text: Message text
            thread_id: Thread/topic ID (optional)
            reply_to: Message ID to reply to (optional)
            media_url: Media URL (optional)
            **kwargs: Platform-specific options

        Returns:
            Platform-specific response with at least:
            - success: bool
            - platform_message_id: str
        """
        pass

    @abstractmethod
    async def _process_raw_message(self, raw: dict[str, Any]) -> Optional[Message]:
        """
        Convert platform-specific raw message to unified Message format.

        Args:
            raw: Raw message from platform SDK

        Returns:
            Normalized Message or None if message should be ignored
        """
        pass

    async def handle_raw_message(self, raw: dict[str, Any]) -> None:
        """
        Process a raw message from the platform and dispatch to handler.

        Args:
            raw: Raw message from platform
        """
        try:
            message = await self._process_raw_message(raw)
            if message is None:
                return

            self.status.last_message_at = datetime.utcnow()
            self.status.messages_processed += 1

            await self.message_handler(message)

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            self.status.errors_count += 1
            raise

    async def start(self) -> None:
        """Start the adapter with state management."""
        async with self._lock:
            if self._state == AdapterState.RUNNING:
                self.logger.warning(f"{self.name} already running")
                return

            self._state = AdapterState.STARTING
            self.status.state = AdapterState.STARTING

            try:
                self._abort_event = asyncio.Event()
                await self.connect()

                self._state = AdapterState.RUNNING
                self.status.state = AdapterState.RUNNING
                self.status.last_start_at = datetime.utcnow()
                self.status.errors_count = 0

                self.logger.info(f"{self.name} adapter started")

            except Exception as e:
                self._state = AdapterState.ERROR
                self.status.state = AdapterState.ERROR
                self.status.last_error = str(e)
                self.logger.error(f"Failed to start {self.name}: {e}")
                raise

    async def stop(self) -> None:
        """Stop the adapter with state management."""
        async with self._lock:
            if self._state == AdapterState.STOPPED:
                return

            self._state = AdapterState.STOPPING
            self.status.state = AdapterState.STOPPING

            try:
                await self.disconnect()

                if self._abort_event:
                    self._abort_event.set()

                self._state = AdapterState.STOPPED
                self.status.state = AdapterState.STOPPED
                self.status.last_stop_at = datetime.utcnow()

                self.logger.info(f"{self.name} adapter stopped")

            except Exception as e:
                self._state = AdapterState.ERROR
                self.status.state = AdapterState.ERROR
                self.status.last_error = str(e)
                self.logger.error(f"Error stopping {self.name}: {e}")
                raise

    def get_status(self) -> AdapterStatus:
        """Get current adapter status."""
        return self.status

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the adapter.

        Returns:
            Health status dict with fields:
            - healthy: bool
            - state: str
            - latency_ms: Optional[float]
        """
        return {
            "healthy": self._state == AdapterState.RUNNING,
            "state": self._state.value,
            "messages_processed": self.status.messages_processed,
            "errors_count": self.status.errors_count,
            "last_message_at": self.status.last_message_at.isoformat() if self.status.last_message_at else None,
        }
