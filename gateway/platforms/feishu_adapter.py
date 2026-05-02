"""
Feishu (Lark) platform adapter (gateway).

- Outbound: Open Platform HTTP APIs (tenant_access_token).
- Inbound (长连接): ``lark-oapi`` WebSocket client — configure the app to
  「使用长连接接收事件」; no public Request URL required.

Optional ``FEISHU_CONNECTION_MODE=http`` disables inbound and keeps send-only API.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)

RECONNECT_DELAYS = (2, 5, 10, 30, 60)


def _http_origin(domain: str) -> str:
    return "https://open.larksuite.com" if domain == "lark" else "https://open.feishu.cn"


def _event_dict_to_message_event(adapter: "FeishuAdapter", payload: dict) -> Optional[MessageEvent]:
    """Build MessageEvent from Lark im.message.receive_v1 JSON (v2 envelope)."""
    ev = payload.get("event")
    if not isinstance(ev, dict):
        return None
    msg = ev.get("message")
    if not isinstance(msg, dict):
        return None

    raw_content = msg.get("content")
    text = ""
    if isinstance(raw_content, str):
        try:
            cj = json.loads(raw_content)
            if isinstance(cj, dict):
                text = str(cj.get("text") or "").strip()
        except json.JSONDecodeError:
            text = raw_content.strip()

    message_id = str(msg.get("message_id") or "")
    chat_id = str(msg.get("chat_id") or ev.get("chat_id") or "").strip()
    chat_type_raw = str(msg.get("chat_type") or ev.get("chat_type") or "p2p").lower()
    is_group = chat_type_raw in ("group", "topic", "chat")

    sender_block = ev.get("sender") if isinstance(ev.get("sender"), dict) else {}
    sid = sender_block.get("sender_id")
    sender_id = ""
    if isinstance(sid, dict):
        sender_id = str(sid.get("open_id") or sid.get("user_id") or "").strip()
    if not sender_id:
        sender_id = str(sender_block.get("id") or "").strip()

    if not chat_id and sender_id:
        chat_id = sender_id

    if not chat_id:
        logger.debug("[feishu] Inbound event missing chat_id; skip")
        return None

    if not text:
        logger.debug("[feishu] Inbound event has no text; skip")
        return None

    source = adapter.build_source(
        chat_id=chat_id,
        chat_type="group" if is_group else "dm",
        user_id=sender_id or None,
        user_name=sender_id or None,
    )

    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=source,
        raw_message=payload,
        message_id=message_id or None,
        timestamp=datetime.now(tz=timezone.utc),
    )


class FeishuAdapter(BasePlatformAdapter):
    """Feishu / Lark adapter with optional WebSocket long connection for inbound events."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.FEISHU)
        extra = config.extra or {}
        self._app_id = str(extra.get("app_id") or "").strip()
        self._app_secret = str(extra.get("app_secret") or "").strip()
        self._domain = str(extra.get("domain") or "feishu").strip().lower()
        if self._domain not in ("feishu", "lark"):
            self._domain = "feishu"
        self._connection_mode = str(
            extra.get("connection_mode") or "websocket"
        ).strip().lower()
        if self._connection_mode not in ("websocket", "http"):
            self._connection_mode = "websocket"
        self._encrypt_key = str(extra.get("encrypt_key") or "").strip()
        self._verification_token = str(extra.get("verification_token") or "").strip()

        self._session: Optional[aiohttp.ClientSession] = None
        self._tenant_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_task: Optional[asyncio.Task] = None

    def _origin(self) -> str:
        return _http_origin(self._domain)

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._tenant_token and time.time() < self._token_expires_at:
            h["Authorization"] = f"Bearer {self._tenant_token}"
        return h

    async def connect(self) -> bool:
        if not self._app_id or not self._app_secret:
            logger.warning("[%s] FEISHU_APP_ID and FEISHU_APP_SECRET required", self.name)
            return False

        self._main_loop = asyncio.get_running_loop()
        self._session = aiohttp.ClientSession()
        await self._refresh_token()
        if not self._tenant_token:
            logger.error("[%s] tenant_access_token failed", self.name)
            await self._close_http()
            return False

        if self._connection_mode == "http":
            self._mark_connected()
            logger.info("[%s] Connected (HTTP send only; no long connection)", self.name)
            return True

        try:
            import lark_oapi  # noqa: F401
        except ImportError:
            logger.error("[%s] Long connection needs lark-oapi: pip install lark-oapi", self.name)
            await self._close_http()
            return False

        self._mark_connected()
        self._ws_task = asyncio.create_task(self._ws_runner(), name="feishu-lark-ws")
        logger.info("[%s] Long connection task started (lark-oapi ws.Client)", self.name)
        return True

    async def _ws_runner(self) -> None:
        """Run blocking lark ws Client in a thread pool; reconnect with backoff."""
        attempt = 0
        while self._running:
            try:
                await asyncio.to_thread(self._blocking_lark_ws_main)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("[%s] WebSocket client exited: %s", self.name, e)
            if not self._running:
                return
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            attempt += 1
            logger.info("[%s] Reconnecting lark ws in %ds...", self.name, delay)
            await asyncio.sleep(delay)

    def _blocking_lark_ws_main(self) -> None:
        import lark_oapi as lark

        enc = self._encrypt_key or ""
        ver = self._verification_token or ""
        handler = (
            lark.EventDispatcherHandler.builder(enc, ver)
            .register_p2_im_message_receive_v1(self._sync_p2_im_message_receive_v1)
            .build()
        )
        domain = (
            getattr(lark, "LARK_DOMAIN", "https://open.larksuite.com")
            if self._domain == "lark"
            else lark.FEISHU_DOMAIN
        )
        cli = lark.ws.Client(
            self._app_id,
            self._app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
            domain=domain,
        )
        cli.start()

    def _sync_p2_im_message_receive_v1(self, data: Any) -> None:
        import lark_oapi as lark

        try:
            raw = lark.JSON.marshal(data)
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            logger.exception("[%s] Failed to marshal P2ImMessageReceiveV1", self.name)
            return

        loop = self._main_loop
        if loop is None:
            return

        fut = asyncio.run_coroutine_threadsafe(self._async_dispatch_p2(payload), loop)
        try:
            fut.result(timeout=300)
        except Exception as e:
            logger.error("[%s] Inbound dispatch failed: %s", self.name, e)

    async def _async_dispatch_p2(self, payload: dict) -> None:
        event = _event_dict_to_message_event(self, payload)
        if event is None:
            return
        await self.handle_message(event)

    async def _close_http(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        self._tenant_token = None

    async def disconnect(self) -> None:
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        await self._close_http()
        self._mark_disconnected()
        logger.info("[%s] Disconnected", self.name)

    async def _refresh_token(self) -> None:
        if not self._session:
            return
        url = f"{self._origin()}/open-apis/auth/v3/tenant_access_token/internal"
        async with self._session.post(
            url,
            json={"app_id": self._app_id, "app_secret": self._app_secret},
        ) as resp:
            if resp.status != 200:
                logger.error("[%s] Token HTTP %s", self.name, resp.status)
                return
            result = await resp.json()
            if result.get("code") == 0:
                self._tenant_token = result.get("tenant_access_token")
                self._token_expires_at = time.time() + 7000
            else:
                logger.error("[%s] Token error: %s", self.name, result)

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        metadata = metadata or {}
        if not self._session:
            return SendResult(success=False, error="Not connected")
        if time.time() >= self._token_expires_at - 60:
            await self._refresh_token()
        if not self._tenant_token:
            return SendResult(success=False, error="No tenant token")

        url = f"{self._origin()}/open-apis/im/v1/messages"
        body: Dict[str, Any] = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": content}),
        }
        if reply_to:
            body["reply_to_message_id"] = reply_to
        if metadata.get("thread_id"):
            body["thread_id"] = metadata["thread_id"]

        try:
            async with self._session.post(
                url,
                json=body,
                params={"receive_id_type": "open_id"},
                headers=self._headers(),
            ) as resp:
                result = await resp.json()
                if result.get("code") != 0:
                    return SendResult(success=False, error=str(result))
                mid = result.get("data", {}).get("message_id")
                return SendResult(success=True, message_id=str(mid) if mid else None, raw_response=result)
        except Exception as e:
            return SendResult(success=False, error=str(e), retryable=True)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": chat_id, "type": "group"}

    # --- Optional HTTP webhook path (not used by long connection) ---

    async def handle_webhook(self, payload: dict[str, Any], headers: Optional[dict] = None) -> None:
        if self._verification_token and payload.get("challenge"):
            return
        if payload.get("header", {}).get("event_type") != "im.message.receive_v1":
            return
        event = _event_dict_to_message_event(self, payload)
        if event:
            await self.handle_message(event)

    def verify_webhook(self, payload: bytes, signature: Optional[str] = None) -> bool:
        if not self._encrypt_key:
            return True
        if not signature:
            return False
        expected = hmac.new(
            self._encrypt_key.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
