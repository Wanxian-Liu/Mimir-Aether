"""
Home Assistant Platform Adapter

Connects to the Home Assistant WebSocket API for real-time event monitoring.
State-change events are converted to Message objects and forwarded to the agent.
Outbound messages are delivered as HA persistent notifications.

Configuration:
- url: Home Assistant URL (default: http://homeassistant.local:8123)
- token: Long-Lived Access Token
- watch_domains: List of HA domains to watch (e.g., ["sensor", "light"])
- watch_entities: List of specific entities to watch
- ignore_entities: List of entities to ignore
- watch_all: Watch all state changes (default: False)
- cooldown_seconds: Minimum time between events for same entity (default: 30)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional, Set

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

from ..adapter import AdapterConfig, AdapterState, AdapterStatus, PlatformAdapter
from ..message import Message, MessageType, ChatType

logger = logging.getLogger(__name__)


def check_ha_requirements() -> bool:
    """Check if Home Assistant dependencies are available."""
    if not AIOHTTP_AVAILABLE:
        return False
    if not os.getenv("HASS_TOKEN"):
        # Check in config as well
        return False
    return True


@dataclass
class HomeAssistantConfig(AdapterConfig):
    """Home Assistant-specific configuration."""

    url: str = "http://homeassistant.local:8123"
    token: str = ""
    watch_domains: list[str] = field(default_factory=list)
    watch_entities: list[str] = field(default_factory=list)
    ignore_entities: list[str] = field(default_factory=list)
    watch_all: bool = False
    cooldown_seconds: int = 30


class HomeAssistantAdapter(PlatformAdapter):
    """
    Home Assistant WebSocket adapter.

    Subscribes to state_changed events and forwards them as Message objects.
    Supports domain/entity filtering and per-entity cooldowns.
    """

    MAX_MESSAGE_LENGTH = 4096

    # Reconnection backoff schedule (seconds)
    _BACKOFF_STEPS = [5, 10, 30, 60]

    def __init__(
        self,
        config: HomeAssistantConfig,
        message_handler: Callable[[Message], Coroutine[Any, Any, None]],
    ):
        super().__init__("homeassistant", config, message_handler)
        self.ha_config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._rest_session: Optional[aiohttp.ClientSession] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._msg_id: int = 0

        # Event filtering
        self._watch_domains: Set[str] = set(config.watch_domains)
        self._watch_entities: Set[str] = set(config.watch_entities)
        self._ignore_entities: Set[str] = set(config.ignore_entities)
        self._watch_all: bool = config.watch_all
        self._cooldown_seconds: int = config.cooldown_seconds

        # Cooldown tracking
        self._last_event_time: dict[str, float] = {}

    def _next_id(self) -> int:
        """Return the next WebSocket message ID."""
        self._msg_id += 1
        return self._msg_id

    async def connect(self) -> None:
        """Connect to Home Assistant WebSocket API."""
        if not AIOHTTP_AVAILABLE:
            logger.warning("[%s] aiohttp not installed. Run: pip install aiohttp", self.name)
            self.status.state = AdapterState.ERROR
            self.status.last_error = "aiohttp not installed"
            return

        token = self.ha_config.token or os.getenv("HASS_TOKEN", "")
        if not token:
            logger.warning("[%s] No HASS_TOKEN configured", self.name)
            self.status.state = AdapterState.ERROR
            self.status.last_error = "No HASS_TOKEN configured"
            return

        try:
            success = await self._ws_connect(token)
            if not success:
                self.status.state = AdapterState.ERROR
                self.status.last_error = "WebSocket connection failed"
                return

            # Dedicated REST session for send() calls
            self._rest_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

            # Warn if no event filters
            if not self._watch_domains and not self._watch_entities and not self._watch_all:
                logger.warning(
                    "[%s] No watch_domains, watch_entities, or watch_all configured. "
                    "All state_changed events will be dropped.",
                    self.name,
                )

            # Start background listener
            self._listen_task = asyncio.create_task(self._listen_loop())
            self._mark_connected()
            logger.info("[%s] Connected to %s", self.name, self.ha_config.url)

        except Exception as e:
            logger.error("[%s] Failed to connect: %s", self.name, e)
            self.status.state = AdapterState.ERROR
            self.status.last_error = str(e)

    def _mark_connected(self) -> None:
        """Mark adapter as connected."""
        self._state = AdapterState.RUNNING
        self.status.state = AdapterState.RUNNING
        self.status.last_start_at = datetime.utcnow()

    async def _ws_connect(self, token: str) -> bool:
        """Establish WebSocket connection and authenticate."""
        url = self.ha_config.url.rstrip("/")
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        self._ws = await self._session.ws_connect(ws_url, heartbeat=30, timeout=30)

        # Step 1: Receive auth_required
        msg = await self._ws.receive_json()
        if msg.get("type") != "auth_required":
            logger.error("Expected auth_required, got: %s", msg.get("type"))
            await self._cleanup_ws()
            return False

        # Step 2: Send auth
        await self._ws.send_json({
            "type": "auth",
            "access_token": token,
        })

        # Step 3: Wait for auth_ok
        msg = await self._ws.receive_json()
        if msg.get("type") != "auth_ok":
            logger.error("Auth failed: %s", msg)
            await self._cleanup_ws()
            return False

        # Step 4: Subscribe to state_changed events
        sub_id = self._next_id()
        await self._ws.send_json({
            "id": sub_id,
            "type": "subscribe_events",
            "event_type": "state_changed",
        })

        # Verify subscription acknowledgement
        msg = await self._ws.receive_json()
        if not msg.get("success"):
            logger.error("Failed to subscribe to events: %s", msg)
            await self._cleanup_ws()
            return False

        return True

    async def _cleanup_ws(self) -> None:
        """Close WebSocket and session."""
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def disconnect(self) -> None:
        """Disconnect from Home Assistant."""
        self._state = AdapterState.STOPPING
        self.status.state = AdapterState.STOPPING

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        await self._cleanup_ws()
        if self._rest_session and not self._rest_session.closed:
            await self._rest_session.close()
        self._rest_session = None

        self._state = AdapterState.STOPPED
        self.status.state = AdapterState.STOPPED
        self.status.last_stop_at = datetime.utcnow()
        logger.info("[%s] Disconnected", self.name)

    async def _listen_loop(self) -> None:
        """Main event loop with automatic reconnection."""
        backoff_idx = 0

        while self._state == AdapterState.RUNNING:
            try:
                await self._read_events()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("[%s] WebSocket error: %s", self.name, e)

            if self._state != AdapterState.RUNNING:
                return

            # Reconnect with backoff
            delay = self._BACKOFF_STEPS[min(backoff_idx, len(self._BACKOFF_STEPS) - 1)]
            logger.info("[%s] Reconnecting in %ds...", self.name, delay)
            await asyncio.sleep(delay)
            backoff_idx += 1

            token = self.ha_config.token or os.getenv("HASS_TOKEN", "")
            try:
                await self._cleanup_ws()
                success = await self._ws_connect(token)
                if success:
                    backoff_idx = 0
                    logger.info("[%s] Reconnected", self.name)
            except Exception as e:
                logger.warning("[%s] Reconnection failed: %s", self.name, e)

    async def _read_events(self) -> None:
        """Read events from WebSocket until disconnected."""
        if not self._ws or self._ws.closed:
            return

        async for ws_msg in self._ws:
            if ws_msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(ws_msg.data)
                    if data.get("type") == "event":
                        await self._handle_ha_event(data.get("event", {}))
                except json.JSONDecodeError:
                    logger.debug("Invalid JSON from HA WS: %s", ws_msg.data[:200])
            elif ws_msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    async def _handle_ha_event(self, event: dict[str, Any]) -> None:
        """Process a state_changed event from Home Assistant."""
        event_data = event.get("data", {})
        entity_id: str = event_data.get("entity_id", "")

        if not entity_id:
            return

        # Apply ignore filter
        if entity_id in self._ignore_entities:
            return

        # Apply domain/entity watch filters
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if self._watch_domains or self._watch_entities:
            domain_match = domain in self._watch_domains if self._watch_domains else False
            entity_match = entity_id in self._watch_entities if self._watch_entities else False
            if not domain_match and not entity_match:
                return
        elif not self._watch_all:
            return

        # Apply cooldown
        now = time.time()
        last = self._last_event_time.get(entity_id, 0)
        if (now - last) < self._cooldown_seconds:
            return
        self._last_event_time[entity_id] = now

        # Build human-readable message
        old_state = event_data.get("old_state", {})
        new_state = event_data.get("new_state", {})
        message = self._format_state_change(entity_id, old_state, new_state)

        if not message:
            return

        # Build Message and forward to handler
        context = MessageContext(
            platform="homeassistant",
            platform_message_id=f"ha_{entity_id}_{int(now)}",
            chat_id="ha_events",
            chat_type=ChatType.CHANNEL,
            sender_id="homeassistant",
            sender_name="Home Assistant",
            raw=event,
        )

        msg_event = Message(
            type=MessageType.TEXT,
            text=message,
            context=context,
            created_at=datetime.fromtimestamp(now),
        )

        await self.message_handler(msg_event)

    @staticmethod
    def _format_state_change(
        entity_id: str,
        old_state: dict[str, Any],
        new_state: dict[str, Any],
    ) -> Optional[str]:
        """Convert a state_changed event into a human-readable description."""
        if not new_state:
            return None

        old_val = old_state.get("state", "unknown") if old_state else "unknown"
        new_val = new_state.get("state", "unknown")

        # Skip if state didn't actually change
        if old_val == new_val:
            return None

        friendly_name = new_state.get("attributes", {}).get("friendly_name", entity_id)
        domain = entity_id.split(".")[0] if "." in entity_id else ""

        # Domain-specific formatting
        if domain == "climate":
            attrs = new_state.get("attributes", {})
            temp = attrs.get("current_temperature", "?")
            target = attrs.get("temperature", "?")
            return (
                f"[Home Assistant] {friendly_name}: HVAC mode changed from "
                f"'{old_val}' to '{new_val}' (current: {temp}, target: {target})"
            )

        if domain == "sensor":
            unit = new_state.get("attributes", {}).get("unit_of_measurement", "")
            return (
                f"[Home Assistant] {friendly_name}: changed from "
                f"{old_val}{unit} to {new_val}{unit}"
            )

        if domain == "binary_sensor":
            return (
                f"[Home Assistant] {friendly_name}: "
                f"{'triggered' if new_val == 'on' else 'cleared'} "
                f"(was {'triggered' if old_val == 'on' else 'cleared'})"
            )

        if domain in ("light", "switch", "fan"):
            return (
                f"[Home Assistant] {friendly_name}: turned "
                f"{'on' if new_val == 'on' else 'off'}"
            )

        if domain == "alarm_control_panel":
            return (
                f"[Home Assistant] {friendly_name}: alarm state changed from "
                f"'{old_val}' to '{new_val}'"
            )

        # Generic fallback
        return (
            f"[Home Assistant] {friendly_name} ({entity_id}): "
            f"changed from '{old_val}' to '{new_val}'"
        )

    async def send_message(
        self,
        chat_id: str,
        text: str,
        thread_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        media_url: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a notification via HA REST API (persistent_notification.create)."""
        token = self.ha_config.token or os.getenv("HASS_TOKEN", "")
        url = f"{self.ha_config.url.rstrip('/')}/api/services/persistent_notification/create"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "title": "MimirAether",
            "message": text[:self.MAX_MESSAGE_LENGTH],
        }

        try:
            if self._rest_session:
                async with self._rest_session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status < 300:
                        return {
                            "success": True,
                            "platform": "homeassistant",
                            "platform_message_id": uuid.uuid4().hex[:12],
                        }
                    else:
                        body = await resp.text()
                        raise RuntimeError(f"HTTP {resp.status}: {body}")
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status < 300:
                            return {
                                "success": True,
                                "platform": "homeassistant",
                                "platform_message_id": uuid.uuid4().hex[:12],
                            }
                        else:
                            body = await resp.text()
                            raise RuntimeError(f"HTTP {resp.status}: {body}")

        except asyncio.TimeoutError:
            raise RuntimeError("Timeout sending notification to HA")
        except Exception as e:
            logger.error("[%s] Send error: %s", self.name, e)
            raise

    async def _process_raw_message(self, raw: dict[str, Any]) -> Optional[Message]:
        """Process raw Home Assistant event."""
        try:
            event_type = raw.get("type", "")
            if event_type == "event":
                event_data = raw.get("event", {})
                event_data_type = event_data.get("event_type", "")
                if event_data_type == "state_changed":
                    await self._handle_ha_event(event_data)
            return None
        except Exception as e:
            logger.error("[%s] Error processing raw message: %s", self.name, e)
            return None
