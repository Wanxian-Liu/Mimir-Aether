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
from gateway.html_to_feishu_card import (
    convert_or_fallback,
    USE_HTML_OUTPUT,
)

logger = logging.getLogger(__name__)

RECONNECT_DELAYS = (2, 5, 10, 30, 60)

# ── Module-level lark SDK availability ────────────────────────
try:
    import lark_oapi as lark  # noqa: F401
    from lark_oapi.core.const import FEISHU_DOMAIN, LARK_DOMAIN  # type: ignore[import-untyped]

    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    FEISHU_DOMAIN = None  # type: ignore[assignment]
    LARK_DOMAIN = None  # type: ignore[assignment]


def _feishu_receive_id_type(chat_id: str) -> str:
    """Lark send message API: receive_id_type must match the ID shape (open_id vs chat_id)."""
    cid = (chat_id or "").strip()
    if cid.startswith("oc_"):
        return "chat_id"
    if cid.startswith("ou_") or cid.startswith("on_"):
        return "open_id"
    # Single-chat / legacy: default to open_id (common for ou_ DMs)
    return "open_id"


def _http_origin(domain: str) -> str:
    return "https://open.larksuite.com" if domain == "lark" else "https://open.feishu.cn"


def _parse_message_content(raw_content: Any) -> dict:
    """统一解析 content 为 dict（可能是 str JSON 或已是 dict）。"""
    if isinstance(raw_content, dict):
        return raw_content
    if isinstance(raw_content, str):
        try:
            parsed = json.loads(raw_content)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {"text": raw_content}  # 纯文本当 text 处理
    return {}

def _feishu_download_image(
    adapter: "FeishuAdapter", image_key: str
) -> Optional[str]:
    """下载飞书图片到本地缓存，返回本地文件路径。

    使用飞书 IM API: GET /open-apis/im/v1/images/{image_key}
    需要 tenant_access_token 认证。
    """
    from gateway.platforms.base import get_image_cache_dir, _looks_like_image, cache_image_from_bytes

    origin = adapter._origin()
    url = f"{origin}/open-apis/im/v1/images/{image_key}"

    # 同步下载（在 WS 处理线程中，不支持 async）
    import time as _time
    import requests

    headers = {}
    if adapter._tenant_token and _time.time() < adapter._token_expires_at:
        headers["Authorization"] = f"Bearer {adapter._tenant_token}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error(
                "[feishu] Image download failed: HTTP %s for key=%s…",
                resp.status_code,
                image_key[:20],
            )
            return None

        data = resp.content
        if not _looks_like_image(data):
            logger.warning(
                "[feishu] Downloaded data does not look like an image (key=%s…, %d bytes)",
                image_key[:20],
                len(data),
            )
            return None

        # Detect extension from content-type or magic bytes
        ct = resp.headers.get("Content-Type", "")
        ext_map = {
            "image/jpeg": ".jpg", "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        ext = ext_map.get(ct, ".jpg")

        path = cache_image_from_bytes(data, ext)
        logger.info(
            "[feishu] Image downloaded: %s (%d bytes, key=%s…)",
            path, len(data), image_key[:20],
        )
        return path
    except requests.Timeout:
        logger.error("[feishu] Image download timeout for key=%s…", image_key[:20])
        return None
    except Exception as e:
        logger.error(
            "[feishu] Image download failed for key=%s…: %s",
            image_key[:20], e,
        )
        return None

def _event_dict_to_message_event(adapter: "FeishuAdapter", payload: dict) -> Optional[MessageEvent]:
    """Build MessageEvent from Lark im.message.receive_v1 JSON (v2 envelope)."""
    ev = payload.get("event")
    if not isinstance(ev, dict):
        return None
    msg = ev.get("message")
    if not isinstance(msg, dict):
        return None

    message_id = str(msg.get("message_id") or "")
    chat_id = str(msg.get("chat_id") or ev.get("chat_id") or "").strip()
    chat_type_raw = str(msg.get("chat_type") or ev.get("chat_type") or "p2p").lower()
    is_group = chat_type_raw in ("group", "topic", "chat")

    sender_block = ev.get("sender") if isinstance(ev.get("sender"), dict) else {}
    st = str(sender_block.get("sender_type", "user")).lower()
    if st == "app":
        logger.debug("[feishu] Skip inbound from app/bot (echo)")
        return None

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

    # 判断消息类型
    msg_type = str(msg.get("message_type") or "text").strip().lower()
    content_dict = _parse_message_content(msg.get("content"))

    # --- 图片消息 ---
    if msg_type == "image":
        image_key = content_dict.get("image_key", "")
        if not image_key:
            logger.warning("[feishu] Image message missing image_key; skip")
            return None

        source = adapter.build_source(
            chat_id=chat_id,
            chat_type="group" if is_group else "dm",
            user_id=sender_id or None,
            user_name=sender_id or None,
        )

        # 同步下载图片（WS 线程中）
        local_path = _feishu_download_image(adapter, image_key)
        if not local_path:
            # 下载失败：仍然返回事件，用 text 说明
            return MessageEvent(
                text="📷 [图片下载失败，请重试]",
                message_type=MessageType.PHOTO,
                source=source,
                raw_message=payload,
                message_id=message_id or None,
                media_urls=[],
                timestamp=datetime.now(tz=timezone.utc),
            )

        return MessageEvent(
            text="",  # 图片消息无文本
            message_type=MessageType.PHOTO,
            source=source,
            raw_message=payload,
            message_id=message_id or None,
            media_urls=[local_path],
            timestamp=datetime.now(tz=timezone.utc),
        )

    # --- 文本消息 ---
    text = str(content_dict.get("text") or "").strip()
    if not text:
        text = str(msg.get("text") or "").strip()

    if not text:
        logger.warning(
            "[feishu] Inbound message has no extractable text (msg_type=%s); keys msg=%s",
            msg.get("message_type"),
            list(msg.keys())[:12],
        )
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

    MAX_MESSAGE_LENGTH = 131072  # 128KB, safe under 150KB Feishu text body limit

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
        self._token_task: Optional[asyncio.Task] = None

        # Exposed for send_message_tool compatibility
        self._domain_name: str = self._domain
        self._client: Any = None  # set by _build_lark_client() when needed

    def _origin(self) -> str:
        return _http_origin(self._domain)

    def _build_lark_client(self, domain: Any) -> Any:
        """Build a lark SDK client for out-of-band API calls (send_message_tool compat).

        Our adapter sends via aiohttp HTTP directly; this client is for
        callers that need the lark SDK object (e.g., listing targets).
        """
        if not FEISHU_AVAILABLE:
            raise RuntimeError(
                "lark-oapi not installed. Run: pip install lark-oapi"
            )
        return (
            lark.Client.builder()
            .app_id(self._app_id)
            .app_secret(self._app_secret)
            .domain(domain)
            .log_level(lark.LogLevel.WARNING)
            .build()
        )

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

        # NOTE: Do NOT import lark_oapi here (on the main event loop thread).
        # lark_oapi.ws.client binds a module-level ``loop`` at import time via
        # ``asyncio.get_event_loop()``. If imported here, it captures the
        # *running* main loop, causing "This event loop is already running"
        # later in the worker thread. All lark_oapi imports happen exclusively
        # inside _blocking_lark_ws_main, after a dedicated event loop is installed.
        self._mark_connected()
        self._ws_task = asyncio.create_task(self._ws_runner(), name="feishu-lark-ws")
        # 启动定时刷新token的后台任务（每60分钟刷新一次，防止过期死锁）
        self._token_task = asyncio.create_task(self._token_refresher(), name="feishu-token-refresh")
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
        # lark_oapi.ws.client binds a module-level ``loop`` at import time via
        # ``asyncio.get_event_loop()``. If that import happened on the gateway's
        # asyncio thread, ``loop`` points at the *running* main loop and
        # ``Client.start()`` → ``run_until_complete`` raises
        # "This event loop is already running". Install a dedicated loop in this
        # worker thread *before* importing the client module (first connect), and
        # always overwrite ``lark_ws_client.loop`` (cached import from main thread).
        ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(ws_loop)
        import lark_oapi.ws.client as lark_ws_client

        lark_ws_client.loop = ws_loop

        import lark_oapi as lark

        enc = self._encrypt_key or ""
        ver = self._verification_token or ""
        # Feishu pushes many IM event types over the same WS. Only
        # ``im.message.receive_v1`` drives the agent; others would trigger
        # lark_oapi "processor not found" ERROR spam. Register no-ops for the
        # noisy types we see in production logs.
        handler = (
            lark.EventDispatcherHandler.builder(enc, ver)
            .register_p2_im_message_receive_v1(self._sync_p2_im_message_receive_v1)
            .register_p2_im_message_message_read_v1(self._lark_noop_message_read_v1)
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
                self._lark_noop_bot_p2p_chat_entered_v1
            )
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

    def _lark_noop_message_read_v1(self, _data: Any) -> None:
        """Read receipts — ignore (keeps lark_oapi from logging processor not found)."""
        logger.debug("[%s] Ignoring im.message.message_read_v1", self.name)

    def _lark_noop_bot_p2p_chat_entered_v1(self, _data: Any) -> None:
        """User entered bot DM — ignore for agent purposes."""
        logger.debug("[%s] Ignoring im.chat.access_event.bot_p2p_chat_entered_v1", self.name)

    async def _token_refresher(self) -> None:
        """后台任务：每60分钟刷新一次飞书 tenant_access_token，防止过期死锁。"""
        while self._running:
            try:
                # 等58分钟（token有效期2小时，提前2小时+缓冲）
                await asyncio.sleep(58 * 60)
                if not self._running:
                    break
                logger.info("[%s] Token refresher: refreshing tenant_access_token", self.name)
                await self._refresh_token()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("[%s] Token refresher error: %s", self.name, e)

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
        if self._token_task:
            self._token_task.cancel()
            try:
                await self._token_task
            except asyncio.CancelledError:
                pass
            self._token_task = None
        await self._close_http()
        self._mark_disconnected()
        logger.info("[%s] Disconnected", self.name)

    async def _refresh_token(self) -> None:
        if not self._session:
            return
        url = f"{self._origin()}/open-apis/auth/v3/tenant_access_token/internal"
        try:
            async with self._session.post(
                url,
                json={"app_id": self._app_id, "app_secret": self._app_secret},
                timeout=aiohttp.ClientTimeout(total=15),
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
        except asyncio.TimeoutError:
            logger.error("[%s] Token refresh timeout", self.name)
        except Exception as e:
            logger.error("[%s] Token refresh failed: %s", self.name, e)

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
        rid_type = metadata.get("feishu_receive_id_type") or _feishu_receive_id_type(chat_id)

        # ── HTML → Feishu Card 检测 ──────────────────────────────
        # 当 USE_HTML_OUTPUT=True 且消息包含 MIMIR:HTML_OUTPUT 标记时，
        # 将 HTML 转换为飞书 interactive 卡片；转换失败自动回退纯文本。
        msg_type = "text"
        msg_content = content
        is_html_card = False
        if USE_HTML_OUTPUT and "<!-- MIMIR:HTML_OUTPUT" in content:
            result = convert_or_fallback(content)
            if result["mode"] == "card":
                payload = result["payload"]
                msg_type = payload.get("msg_type", "interactive")
                msg_content = payload.get("content", "")
                is_html_card = True
                logger.info(
                    "[%s] HTML→Card conversion succeeded, sending as interactive",
                    self.name,
                )
            else:
                # 回退到纯文本
                msg_content = result.get("payload", content)
                logger.info(
                    "[%s] HTML→Card fallback: %s",
                    self.name,
                    result.get("fallback_reason", "unknown"),
                )
        # ─────────────────────────────────────────────────────────

        body: Dict[str, Any] = {
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": msg_content if is_html_card else json.dumps({"text": msg_content}),
        }
        if reply_to:
            body["reply_to_message_id"] = reply_to
        if metadata.get("thread_id"):
            body["thread_id"] = metadata["thread_id"]

        try:
            async with self._session.post(
                url,
                json=body,
                params={"receive_id_type": rid_type},
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
                if result.get("code") != 0:
                    logger.warning(
                        "[%s] send failed receive_id_type=%s chat_id=%s… api=%s",
                        self.name,
                        rid_type,
                        (chat_id or "")[:24],
                        result,
                    )
                    return SendResult(success=False, error=str(result))
                mid = result.get("data", {}).get("message_id")
                logger.info(
                    "[%s] send success message_id=%s chat_id=%s…",
                    self.name,
                    str(mid)[:24] if mid else "?",
                    (chat_id or "")[:24],
                )
                return SendResult(success=True, message_id=str(mid) if mid else None, raw_response=result)
        except asyncio.TimeoutError:
            logger.error(
                "[%s] send timeout (30s) receive_id_type=%s chat_id=%s…",
                self.name,
                rid_type,
                (chat_id or "")[:24],
            )
            return SendResult(success=False, error="send timeout", retryable=True)
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
