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
import os
import threading
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


def _tracked_task(name: str, coro):
    """P0-1: 包装 asyncio Task，确保静默异常被记录。

    asyncio.create_task() 创建的 Task 如果抛出未被捕获的异常，
    默认只在 Task 被 GC 时打印一条难以追踪的警告。
    此包装器将异常提升为 logger.error，包含完整的 traceback。
    """

    async def _runner():
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[feishu] TrackedTask %s crashed", name)
            raise

    return asyncio.create_task(_runner(), name=name)


class CircuitBreaker:
    """P0-2: 三态断路器，WS 重连保底。

    CLOSED  → 正常请求，失败累积
    OPEN    → 熔断中，拒绝所有请求
    HALF_OPEN → 试探窗口，允许一个请求通过测试
    """

    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    def __init__(self, max_failures: int = 5, reset_timeout: float = 60.0):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._tripped_at: float = 0.0

    def allow_request(self) -> bool:
        """是否可以发起请求。OPEN→HALF_OPEN 自动转换。"""
        import time as _time
        now = _time.time()
        if self._state == self.STATE_CLOSED:
            return True
        if self._state == self.STATE_OPEN:
            if now - self._tripped_at >= self.reset_timeout:
                self._state = self.STATE_HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one probe
        return True

    def on_success(self):
        """请求成功：重置到 CLOSED。"""
        self._state = self.STATE_CLOSED
        self._failure_count = 0

    def on_failure(self):
        """请求失败：记录并判断是否熔断。"""
        import time as _time
        now = _time.time()
        self._failure_count += 1
        self._last_failure_time = now
        if self._state == self.STATE_HALF_OPEN:
            # 试探失败 → 立即重新熔断
            self._state = self.STATE_OPEN
            self._tripped_at = now
        elif self._failure_count >= self.max_failures:
            self._state = self.STATE_OPEN
            self._tripped_at = now

    def time_until_reset(self) -> float:
        """距离 HALF_OPEN 还有多少秒；不在 OPEN 状态返回 0。"""
        import time as _time
        if self._state != self.STATE_OPEN:
            return 0.0
        elapsed = _time.time() - self._tripped_at
        return max(0.0, self.reset_timeout - elapsed)

    @property
    def state(self) -> str:
        return self._state

# ── Token refresh 护栏 ─────────────────────────────────────
# tenant_access_token 有效期 ~2h；API 返回 expire 约 6000-7200s。
# 后台 _token_refresher 每 30 分钟刷新一次（防御：asyncio 任务静默停止）。
# 发送路径 (send) 额外检查：距离上次成功刷新 > 90 分钟则强制刷新，
# 防止 _token_expires_at 硬编码 7000s 与 API 实际 expire 不一致导致的过期漏检。
TOKEN_REFRESH_INTERVAL = 30 * 60      # 30 min
TOKEN_STALE_THRESHOLD = 90 * 60       # 90 min — send() emergency refresh
TOKEN_EXPIRE_FALLBACK = 7000          # 2h-ish fallback if API omits expire

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


def _tenant_token_valid(adapter: "FeishuAdapter", *, buffer_seconds: int = 60) -> bool:
    """True when tenant_access_token is present and not within expiry buffer."""
    with adapter._token_lock:
        token = adapter._tenant_token
        expires_at = adapter._token_expires_at
    if not token:
        return False
    return time.time() < expires_at - buffer_seconds


def _feishu_download_image(
    adapter: "FeishuAdapter",
    image_key: str,
    *,
    message_id: str = "",
) -> Optional[str]:
    """下载飞书图片到本地缓存，返回本地文件路径。

  入站用户图片：GET /im/v1/messages/{message_id}/resources/{file_key}?type=image
  机器人上传图：GET /im/v1/images/{image_key}（仅上传方可拉取，对用户图会 400）
    """
    from gateway.platforms.base import _looks_like_image, cache_image_from_bytes

    origin = adapter._origin()
    urls: list[str] = []
    mid = (message_id or "").strip()
    if mid:
        urls.append(
            f"{origin}/open-apis/im/v1/messages/{mid}/resources/{image_key}?type=image"
        )
    urls.append(f"{origin}/open-apis/im/v1/images/{image_key}")

    import requests

    if not adapter._ensure_tenant_token_sync():
        logger.error(
            "[feishu] Image download aborted: tenant_access_token unavailable (key=%s…)",
            image_key[:20],
        )
        return None

    try:
        resp = None
        for url_idx, url in enumerate(urls):
            ok = False
            for attempt in range(2):
                headers = {}
                with adapter._token_lock:
                    local_token = adapter._tenant_token
                if local_token:
                    headers["Authorization"] = f"Bearer {local_token}"

                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code == 200:
                    ok = True
                    break
                if attempt == 0 and resp.status_code in (400, 401, 403):
                    logger.info(
                        "[feishu] Image download HTTP %s (url #%d); refreshing tenant token and retrying",
                        resp.status_code,
                        url_idx + 1,
                    )
                    if adapter._refresh_token_sync():
                        continue
                logger.warning(
                    "[feishu] Image download HTTP %s for key=%s… (url #%d)",
                    resp.status_code,
                    image_key[:20],
                    url_idx + 1,
                )
                break
            if ok:
                break
        else:
            logger.error(
                "[feishu] Image download failed for key=%s… (tried %d URL(s))",
                image_key[:20],
                len(urls),
            )
            return None

        if resp is None or resp.status_code != 200:
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


async def _feishu_download_image_async(
    adapter: "FeishuAdapter",
    image_key: str,
    *,
    message_id: str = "",
) -> Optional[str]:
    """Async variant of _feishu_download_image — uses aiohttp, does NOT block event loop."""
    from gateway.platforms.base import _looks_like_image, cache_image_from_bytes

    origin = adapter._origin()
    urls: list[str] = []
    mid = (message_id or "").strip()
    if mid:
        urls.append(
            f"{origin}/open-apis/im/v1/messages/{mid}/resources/{image_key}?type=image"
        )
    urls.append(f"{origin}/open-apis/im/v1/images/{image_key}")

    session = adapter._session
    if not session:
        logger.error("[feishu] Async image download aborted: no aiohttp session (key=%s…)", image_key[:20])
        return None

    with adapter._token_lock:
        local_token = adapter._tenant_token
    if not local_token:
        if not adapter._ensure_tenant_token_sync():
            logger.error("[feishu] Async image download aborted: no tenant token (key=%s…)", image_key[:20])
            return None
        with adapter._token_lock:
            local_token = adapter._tenant_token

    resp = None
    for url_idx, url in enumerate(urls):
        ok = False
        for attempt in range(2):
            headers = {}
            with adapter._token_lock:
                t = adapter._tenant_token
            if t:
                headers["Authorization"] = f"Bearer {t}"
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        data = await r.read()
                        resp = type('Resp', (), {'status_code': 200, 'content': data, 'headers': dict(r.headers)})()
                        ok = True
                        break
                    if attempt == 0 and r.status in (400, 401, 403):
                        logger.info(
                            "[feishu] Async image download HTTP %s (url #%d); refreshing token and retrying",
                            r.status, url_idx + 1,
                        )
                        await adapter._refresh_token()
                        continue
                    logger.warning("[feishu] Async image download HTTP %s for key=%s… (url #%d)", r.status, image_key[:20], url_idx + 1)
                    break
            except asyncio.TimeoutError:
                logger.error("[feishu] Async image download timeout for key=%s… (url #%d)", image_key[:20], url_idx + 1)
                break
        if ok:
            break
    else:
        logger.error("[feishu] Async image download failed for key=%s…", image_key[:20])
        return None

    if resp is None or resp.status_code != 200:
        return None
    data = resp.content
    if not _looks_like_image(data):
        logger.warning("[feishu] Async downloaded data does not look like an image (key=%s…, %d bytes)", image_key[:20], len(data))
        return None

    ct = resp.headers.get("Content-Type", "")
    ext_map = {
        "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
        "image/gif": "gif", "image/webp": "webp", "image/bmp": "bmp",
    }
    ext = "jpg"
    for mime, e in ext_map.items():
        if mime in ct:
            ext = e
            break
    path = cache_image_from_bytes(data, image_key, ext=ext)
    logger.info("[feishu] Image downloaded (async): %s (%d bytes, key=%s…)", path, len(data), image_key[:20])
    return path


def _event_dict_to_message_event(
    adapter: "FeishuAdapter",
    payload: dict,
    *,
    pre_downloaded_path: Optional[str] = None,
) -> Optional[MessageEvent]:
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

        # 下载图片（优先使用预下载路径，避免阻塞事件循环）
        if pre_downloaded_path is not None:
            local_path = pre_downloaded_path if pre_downloaded_path else None
        else:
            local_path = _feishu_download_image(adapter, image_key, message_id=message_id)
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

    # --- 富文本（post）消息：文本在 content.content[行][元素].text ---
    text = ""
    if msg_type == "post":
        post_lines = content_dict.get("content", [])
        post_texts = []
        for line in post_lines:
            if isinstance(line, list):
                for elem in line:
                    if isinstance(elem, dict) and elem.get("tag") in ("text", "a"):
                        t = elem.get("text", "")
                        if t:
                            post_texts.append(t)
            elif isinstance(line, dict) and line.get("text"):
                post_texts.append(str(line["text"]))
        text = "".join(post_texts).strip()
        if not text:
            # post 也可能带 title
            text = str(content_dict.get("title") or "").strip()

    # --- 文本消息 ---
    if not text:
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
        self._token_lock = threading.Lock()  # P0-1: 保护 _tenant_token 三字段并发读写
        self._ws_shutdown = threading.Event()  # P0-3: WS 线程退出信号
        self._ws_thread: Optional[threading.Thread] = None  # P0-3: WS 线程引用，用于 disconnect() 等待退出
        self._ws_breaker = CircuitBreaker(max_failures=5, reset_timeout=60.0)  # P0-2: WS 重连断路器
        self._tenant_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._last_token_refresh_at: float = 0.0  # 上次成功刷新时间戳（send() 护栏用）
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._token_task: Optional[asyncio.Task] = None

        # Exposed for send_message_tool compatibility
        self._domain_name: str = self._domain
        self._client: Any = None  # set by _build_lark_client() when needed

        # 2026-08-25 fix-card change4: read receipts (liuge requirement 8/24)
        self._read_receipts: Dict[str, dict] = {}  # message_id -> {reader_id, reader_type, read_at}
        self._sent_msg_chat: Dict[str, str] = {}  # message_id -> chat_id (recorded on send ok)
        self._last_read_feedback_at: Dict[str, float] = {}  # chat_id -> last feedback ts (60s throttle)

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
        with self._token_lock:
            token = self._tenant_token
            expired = time.time() >= self._token_expires_at - 60
        if token and not expired:
            h["Authorization"] = f"Bearer {token}"
        return h

    def _ensure_tenant_token_sync(self) -> bool:
        """Ensure tenant_access_token for sync paths (image download)."""
        if _tenant_token_valid(self):
            return True
        return self._refresh_token_sync()

    def _refresh_token_sync(self) -> bool:
        """Refresh tenant_access_token without aiohttp (safe from sync inbound handlers)."""
        import requests

        if not self._app_id or not self._app_secret:
            logger.error("[%s] Cannot refresh token: missing app_id/app_secret", self.name)
            return False

        url = f"{self._origin()}/open-apis/auth/v3/tenant_access_token/internal"
        try:
            resp = requests.post(
                url,
                json={"app_id": self._app_id, "app_secret": self._app_secret},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("[%s] Token HTTP %s (sync)", self.name, resp.status_code)
                return False
            result = resp.json()
            if result.get("code") == 0:
                with self._token_lock:
                    self._tenant_token = result.get("tenant_access_token")
                    api_expire = result.get("expire", 0)
                    self._token_expires_at = time.time() + (api_expire if api_expire > 0 else TOKEN_EXPIRE_FALLBACK)
                    self._last_token_refresh_at = time.time()
                    ok = bool(self._tenant_token)
                return ok
            logger.error("[%s] Token error (sync): %s", self.name, result)
            return False
        except requests.Timeout:
            logger.error("[%s] Token refresh timeout (sync)", self.name)
            return False
        except Exception as e:
            logger.error("[%s] Token refresh failed (sync): %s", self.name, e)
            return False

    async def connect(self) -> bool:
        if not self._app_id or not self._app_secret:
            logger.warning("[%s] FEISHU_APP_ID and FEISHU_APP_SECRET required", self.name)
            return False

        self._main_loop = asyncio.get_running_loop()
        self._session = aiohttp.ClientSession()
        await self._refresh_token()
        with self._token_lock:
            has_token = bool(self._tenant_token)
        if not has_token:
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
        self._ws_task = _tracked_task("feishu-lark-ws", self._ws_runner())
        # 启动定时刷新token的后台任务（每60分钟刷新一次，防止过期死锁）
        self._token_task = _tracked_task("feishu-token-refresh", self._token_refresher())
        logger.info("[%s] Long connection task started (lark-oapi ws.Client)", self.name)
        return True

    async def _ws_runner(self) -> None:
        """Run blocking lark ws Client in a thread pool; reconnect with backoff."""
        attempt = 0
        breaker = self._ws_breaker
        while self._running and not self._ws_shutdown.is_set():
            # P0-2: 断路器——连续失败 5 次则熔断 60s，防止资源泄漏
            if not breaker.allow_request():
                wait = breaker.time_until_reset()
                logger.warning(
                    "[%s] Circuit breaker %s; sleeping %.0fs for HALF_OPEN",
                    self.name, breaker.state, wait,
                )
                await asyncio.sleep(wait)
                continue
            try:
                self._ws_shutdown.clear()
                await asyncio.to_thread(self._blocking_lark_ws_main)
                breaker.on_success()
                attempt = 0
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("[%s] WebSocket client exited: %s", self.name, e)
                breaker.on_failure()
            if not self._running or self._ws_shutdown.is_set():
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
        # \"This event loop is already running\". Install a dedicated loop in this
        # worker thread *before* importing the client module (first connect), and
        # always overwrite ``lark_ws_client.loop`` (cached import from main thread).
        self._ws_thread = threading.current_thread()
        if self._ws_shutdown.is_set():
            return
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

    def _lark_noop_message_read_v1(self, data: Any) -> None:
        """Read receipts — 2026-08-25 fix-card change4: track read state and give a
        lightweight read feedback in the Feishu chat (liuge 8/24: others show a read
        avatar, Mimir does not — make read state perceivable). 60s throttle."""
        try:
            import lark_oapi as lark
            raw = lark.JSON.marshal(data)
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            logger.exception("[%s] Failed to marshal P2ImMessageMessageReadV1", self.name)
            return
        ev = payload.get("event", {}) if isinstance(payload, dict) else {}
        reader = ev.get("reader", {}) or {}
        reader_id = str(reader.get("reader_id") or "")
        reader_type = str(reader.get("reader_type") or "")
        msg_ids = ev.get("message_id_list") or []
        if not msg_ids:
            logger.debug("[%s] message_read_v1: empty message_id_list", self.name)
            return
        now = time.time()
        for mid in msg_ids:
            self._read_receipts[str(mid)] = {
                "reader_id": reader_id,
                "reader_type": reader_type,
                "read_at": now,
            }
        logger.info(
            "[%s] message_read_v1: reader=%s type=%s messages=%d (read receipts tracked)",
            self.name, reader_id, reader_type, len(msg_ids),
        )
        chat_id = self._sent_msg_chat.get(str(msg_ids[0])) if msg_ids else None
        if not chat_id:
            return
        _now = time.time()
        if _now - self._last_read_feedback_at.get(chat_id, 0.0) < 60.0:
            return
        self._last_read_feedback_at[chat_id] = _now
        loop = self._main_loop
        if loop is None:
            return

        async def _send_read_feedback() -> None:
            try:
                await self.send(chat_id, "已读你的消息（Mimir 已收到）")
            except Exception as exc:
                logger.warning("[%s] read feedback send failed: %s", self.name, exc)

        fut = asyncio.run_coroutine_threadsafe(_send_read_feedback(), loop)

        def _log_err(done: asyncio.Future) -> None:
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None:
                logger.error("[%s] read feedback send error: %s", self.name, exc)

        fut.add_done_callback(_log_err)

    def _lark_noop_bot_p2p_chat_entered_v1(self, _data: Any) -> None:
        """User entered bot DM — ignore for agent purposes."""
        logger.debug("[%s] Ignoring im.chat.access_event.bot_p2p_chat_entered_v1", self.name)

    async def _token_refresher(self) -> None:
        """后台任务：每30分钟刷新一次飞书 tenant_access_token，带心跳日志防静默停止。"""
        _heartbeat_interval = 10 * 60  # 每10分钟打一次心跳
        _next_heartbeat = time.time() + _heartbeat_interval
        while self._running:
            try:
                await asyncio.sleep(min(TOKEN_REFRESH_INTERVAL, _heartbeat_interval))
                if not self._running:
                    break
                now = time.time()
                # 心跳：证明 refresher 没死
                refresh_due = (
                    self._last_token_refresh_at == 0.0
                    or (now - self._last_token_refresh_at) >= TOKEN_REFRESH_INTERVAL
                )
                if refresh_due:
                    logger.info("[%s] Token refresher: refreshing tenant_access_token", self.name)
                    await self._refresh_token()
                    _next_heartbeat = now + _heartbeat_interval
                elif now >= _next_heartbeat:
                    logger.debug("[%s] Token refresher: alive (token age=%.0fs)", self.name, now - self._last_token_refresh_at)
                    _next_heartbeat = now + _heartbeat_interval
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

        # STAB-01: Do not block the lark ws worker thread on agent turns.
        # Blocking fut.result() here prevented WS ping/pong during long inference
        # (Gateway #1 / #25). Dispatch on the gateway main loop; log failures async.
        fut = asyncio.run_coroutine_threadsafe(self._async_dispatch_p2(payload), loop)

        def _log_dispatch_error(done: asyncio.Future) -> None:
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None:
                logger.error("[%s] Inbound dispatch failed: %s", self.name, exc)

        fut.add_done_callback(_log_dispatch_error)

    async def _async_dispatch_p2(self, payload: dict) -> None:
        # P0-4: 图片消息在主事件循环中处理──先用 aiohttp 异步下载，避免阻塞
        pre_downloaded = None
        ev = payload.get("event", {}) if isinstance(payload, dict) else {}
        msg = ev.get("message", {}) if isinstance(ev, dict) else {}
        if isinstance(msg, dict) and str(msg.get("message_type", "")).strip().lower() == "image":
            content_dict = _parse_message_content(msg.get("content"))
            image_key = content_dict.get("image_key", "")
            if image_key:
                pre_downloaded = await _feishu_download_image_async(
                    self, image_key, message_id=str(msg.get("message_id", ""))
                )
                if not pre_downloaded:
                    # 下载失败时传空字符串，让 _event_dict_to_message_event 用 fallback text
                    pre_downloaded = ""

        event = _event_dict_to_message_event(self, payload, pre_downloaded_path=pre_downloaded)
        if event is None:
            return
        # 发送 typing 指示器
        chat_id = str(payload.get("event", {}).get("message", {}).get("chat_id", "") or 
                      payload.get("event", {}).get("chat_id", ""))
        if chat_id:
            try:
                await self.send_typing(chat_id)
            except Exception:
                pass  # typing 失败不影响消息处理
        await self.handle_message(event)

    async def _close_http(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        with self._token_lock:
            self._tenant_token = None

    async def disconnect(self) -> None:
        self._running = False
        self._ws_shutdown.set()  # P0-3: 通知 WS 线程退出
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        # P0-3: 等待底层 OS 线程实际退出，防止线程泄漏累积
        ws_thread = self._ws_thread
        if ws_thread is not None and ws_thread.is_alive():
            ws_thread.join(timeout=5)
            if ws_thread.is_alive():
                logger.warning("[%s] WS thread did not exit within 5s timeout", self.name)
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
                    with self._token_lock:
                        self._tenant_token = result.get("tenant_access_token")
                        api_expire = result.get("expire", 0)
                        self._token_expires_at = time.time() + (api_expire if api_expire > 0 else TOKEN_EXPIRE_FALLBACK)
                        self._last_token_refresh_at = time.time()
                else:
                    logger.error("[%s] Token error: %s", self.name, result)
        except asyncio.TimeoutError:
            logger.error("[%s] Token refresh timeout", self.name)
        except Exception as e:
            logger.error("[%s] Token refresh failed: %s", self.name, e)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """飞书 typing 指示器"""
        if not self._session:
            return
        with self._token_lock:
            token = self._tenant_token
        if not token:
            return
        try:
            url = f"{self._origin()}/open-apis/im/v1/typing"
            async with self._session.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"chat_id": chat_id, "status": "Begin"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status not in (200, 204):
                    logger.debug("[feishu] typing indicator returned HTTP %s", r.status)
        except Exception:
            pass

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
        # 双保险：token 过期 OR 上次刷新超过阈值 → 强制刷新
        token_expired = not _tenant_token_valid(self)
        token_stale = (
            self._last_token_refresh_at > 0.0
            and (time.time() - self._last_token_refresh_at) > TOKEN_STALE_THRESHOLD
        )
        if token_expired or token_stale:
            if token_stale:
                logger.warning(
                    "[%s] Token stale (last refresh %.0fs ago), emergency refresh",
                    self.name, time.time() - self._last_token_refresh_at,
                )
            await self._refresh_token()
        with self._token_lock:
            has_token = bool(self._tenant_token)
        if not has_token:
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

        # ── Pre-Send Verify Gate (2026-07-29 4-agent discussion) ──
        # Block any "done"/"written"/"landed" claim unless
        # the claimed files actually exist on disk with size > 0.
        _CLAIM_KW = ("已完成", "已写入", "已落地", "三块基线", "全部落盘")
        if any(kw in content for kw in _CLAIM_KW):
            import os as _os, pathlib as _pl, json as _json
            session_log = _pl.Path("~/.mimiraether/data/raw_session_logs.jsonl").expanduser()
            recent_paths = set()
            if session_log.exists():
                for line in session_log.read_text().rstrip().split("\n")[-10:]:
                    try:
                        rec = _json.loads(line)
                        if rec.get("tool") == "write_file" and rec.get("status") == "success":
                            path = rec.get("path") or rec.get("file") or ""
                            if path:
                                recent_paths.add(_pl.Path(path).expanduser())
                    except Exception:
                        pass
            if recent_paths:
                missing = [str(p) for p in recent_paths if not p.exists() or p.stat().st_size == 0]
                if missing:
                    raise RuntimeError(
                        f"Pre-send verify BLOCKED: {len(missing)} file(s) in recent "
                        f"write_file claims not on disk or empty: {missing[:3]}"
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
                # 2026-08-25 fix-card change4: map message_id -> chat_id for read feedback
                if mid:
                    self._sent_msg_chat[str(mid)] = chat_id
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

    async def send_file(
        self,
        chat_id: str,
        file_path: str,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload and send a file to a Feishu chat.

        Two-step flow:
          1. POST /open-apis/im/v1/files (multipart upload) → file_key
          2. POST /open-apis/im/v1/messages (msg_type=file) → deliver

        Args:
            chat_id: Target chat ID.
            file_path: Absolute path to the file on disk.
            file_name: Display name in chat (default: basename of file_path).
            reply_to: Optional message ID to reply to.
            metadata: Optional dict (supports feishu_receive_id_type override).

        Returns:
            SendResult with success status and message_id.
        """
        if not self._session:
            return SendResult(success=False, error="Not connected")
        token_expired = not _tenant_token_valid(self)
        token_stale = (
            self._last_token_refresh_at > 0.0
            and (time.time() - self._last_token_refresh_at) > TOKEN_STALE_THRESHOLD
        )
        if token_expired or token_stale:
            await self._refresh_token()
        with self._token_lock:
            token = self._tenant_token
        if not token:
            return SendResult(success=False, error="No tenant token")

        display_name = file_name or os.path.basename(file_path)

        # ── Step 1: upload file ─────────────────────────────────
        upload_url = f"{self._origin()}/open-apis/im/v1/files"
        try:
            with open(file_path, "rb") as fh:
                file_data = fh.read()
        except FileNotFoundError:
            return SendResult(success=False, error=f"File not found: {file_path}")
        except OSError as e:
            return SendResult(success=False, error=str(e))

        from aiohttp import FormData
        form = FormData()
        form.add_field("file_type", "stream")
        form.add_field("file_name", display_name)
        form.add_field("file", file_data, filename=display_name, content_type="application/octet-stream")

        try:
            async with self._session.post(
                upload_url,
                data=form,
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                upload_result = await resp.json()
                if upload_result.get("code") != 0:
                    logger.warning(
                        "[%s] file upload failed: %s",
                        self.name, upload_result,
                    )
                    return SendResult(
                        success=False,
                        error=f"Upload failed: {upload_result.get('msg', 'unknown')}",
                    )
                file_key = upload_result.get("data", {}).get("file_key")
                if not file_key:
                    return SendResult(success=False, error="No file_key in upload response")
        except asyncio.TimeoutError:
            return SendResult(success=False, error="Upload timeout", retryable=True)
        except Exception as e:
            return SendResult(success=False, error=str(e), retryable=True)

        logger.info(
            "[%s] file uploaded file_key=%s name=%s size=%d",
            self.name, file_key, display_name, len(file_data),
        )

        # ── Step 2: send file message ───────────────────────────
        msg_url = f"{self._origin()}/open-apis/im/v1/messages"
        rid_type = metadata.get("feishu_receive_id_type") or _feishu_receive_id_type(chat_id) if metadata else _feishu_receive_id_type(chat_id)

        body: Dict[str, Any] = {
            "receive_id": chat_id,
            "msg_type": "file",
            "content": json.dumps({"file_key": file_key}),
        }
        if reply_to:
            body["reply_to_message_id"] = reply_to
        if metadata and metadata.get("thread_id"):
            body["thread_id"] = metadata["thread_id"]

        try:
            async with self._session.post(
                msg_url,
                json=body,
                params={"receive_id_type": rid_type},
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
                if result.get("code") != 0:
                    logger.warning(
                        "[%s] send file message failed: %s",
                        self.name, result,
                    )
                    return SendResult(success=False, error=str(result))
                mid = result.get("data", {}).get("message_id")
                logger.info(
                    "[%s] file sent message_id=%s file_key=%s",
                    self.name, str(mid)[:24] if mid else "?", file_key,
                )
                return SendResult(success=True, message_id=str(mid) if mid else None, raw_response=result)
        except asyncio.TimeoutError:
            return SendResult(success=False, error="Send file message timeout", retryable=True)
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
            # 发送 typing 指示器
            chat_id = str(payload.get("event", {}).get("message", {}).get("chat_id", "") or 
                          payload.get("event", {}).get("chat_id", ""))
            if chat_id:
                try:
                    await self.send_typing(chat_id)
                except Exception:
                    pass
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
