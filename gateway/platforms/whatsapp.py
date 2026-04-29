"""
WhatsApp Platform Adapter

WhatsApp integration via Node.js bridge (whatsapp-web.js or Baileys).
Messages are forwarded via HTTP/IPC between the bridge and this adapter.

This adapter supports multiple backends:
1. WhatsApp Business API (requires Meta verification)
2. whatsapp-web.js (via Node.js subprocess) - for personal accounts
3. Baileys (via Node.js subprocess) - alternative for personal accounts

Configuration:
- bridge_script: Path to the Node.js bridge script
- bridge_port: Port for HTTP communication (default: 3000)
- session_path: Path to store WhatsApp session data
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

import aiohttp

from ..adapter import AdapterConfig, AdapterState, AdapterStatus, PlatformAdapter
from ..message import Message, MessageType, ChatType

_IS_WINDOWS = platform.system() == "Windows"

logger = logging.getLogger(__name__)


def _kill_port_process(port: int) -> None:
    """Kill any process listening on the given TCP port."""
    try:
        if _IS_WINDOWS:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3] == "LISTENING":
                    local_addr = parts[1]
                    if local_addr.endswith(f":{port}"):
                        try:
                            subprocess.run(
                                ["taskkill", "/PID", parts[4], "/F"],
                                capture_output=True, timeout=5,
                            )
                        except subprocess.SubprocessError:
                            pass
        else:
            result = subprocess.run(
                ["fuser", f"{port}/tcp"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    capture_output=True, timeout=5,
                )
    except Exception:
        pass


def check_whatsapp_requirements() -> bool:
    """Check if WhatsApp dependencies are available."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


@dataclass
class WhatsAppConfig(AdapterConfig):
    """WhatsApp-specific configuration."""

    bridge_script: str = ""
    bridge_port: int = 3000
    session_path: str = ""
    reply_prefix: Optional[str] = None
    require_mention: bool = False
    free_response_chats: list[str] = field(default_factory=list)
    mention_patterns: list[str] = field(default_factory=list)


class WhatsAppAdapter(PlatformAdapter):
    """
    WhatsApp adapter using Node.js bridge.

    This implementation uses a HTTP bridge pattern where:
    1. A Node.js process runs the WhatsApp Web client
    2. Messages are forwarded via HTTP/IPC to this Python adapter
    3. Responses are sent back through the bridge
    """

    # WhatsApp message limits — practical UX limit, not protocol max.
    MAX_MESSAGE_LENGTH = 4096

    # Default bridge location
    _DEFAULT_BRIDGE_DIR = Path(__file__).resolve().parents[2] / "scripts" / "whatsapp-bridge"

    def __init__(
        self,
        config: WhatsAppConfig,
        message_handler: Callable[[Message], Coroutine[Any, Any, None]],
    ):
        super().__init__("whatsapp", config, message_handler)
        self.whatsapp_config = config
        self._bridge_process: Optional[subprocess.Popen] = None
        self._bridge_port = config.bridge_port
        self._session_path = Path(config.session_path) if config.session_path else self._DEFAULT_BRIDGE_DIR.parent / "whatsapp_session"
        self._bridge_log_fh = None
        self._bridge_log: Optional[Path] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._mention_patterns = self._compile_mention_patterns()

    def _compile_mention_patterns(self):
        """Compile mention patterns from config."""
        patterns = self.whatsapp_config.mention_patterns
        if not patterns:
            return []
        compiled = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                continue
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error as exc:
                logger.warning("[%s] Invalid mention pattern %r: %s", self.name, pattern, exc)
        return compiled

    @staticmethod
    def _normalize_whatsapp_id(value: Optional[str]) -> str:
        """Normalize WhatsApp ID format."""
        if not value:
            return ""
        normalized = str(value).strip()
        if ":" in normalized and "@" in normalized:
            normalized = normalized.replace(":", "@", 1)
        return normalized

    def _bot_ids_from_message(self, data: dict[str, Any]) -> set:
        """Extract bot IDs from message data."""
        bot_ids = set()
        for candidate in data.get("botIds") or []:
            normalized = self._normalize_whatsapp_id(candidate)
            if normalized:
                bot_ids.add(normalized)
        return bot_ids

    def _message_mentions_bot(self, data: dict[str, Any]) -> bool:
        """Check if message mentions the bot."""
        bot_ids = self._bot_ids_from_message(data)
        if not bot_ids:
            return False
        mentioned_ids = {
            nid
            for candidate in (data.get("mentionedIds") or [])
            if (nid := self._normalize_whatsapp_id(candidate))
        }
        if mentioned_ids & bot_ids:
            return True
        body = str(data.get("body") or "")
        lower_body = body.lower()
        for bot_id in bot_ids:
            bare_id = bot_id.split("@", 1)[0].lower()
            if bare_id and (f"@{bare_id}" in lower_body or bare_id in lower_body):
                return True
        return False

    def _should_process_message(self, data: dict[str, Any]) -> bool:
        """Determine if message should be processed."""
        if not data.get("isGroup"):
            return True
        chat_id = str(data.get("chatId") or "")
        if chat_id in self.whatsapp_config.free_response_chats:
            return True
        if not self.whatsapp_config.require_mention:
            return True
        body = str(data.get("body") or "").strip()
        if body.startswith("/"):
            return True
        if self._message_mentions_bot(data):
            return True
        return False

    def format_message(self, content: str) -> str:
        """Convert markdown to WhatsApp-compatible formatting."""
        if not content:
            return content

        # Protect fenced code blocks
        _FENCE_PH = "\x00FENCE"
        fences: list[str] = []

        def _save_fence(m: re.Match) -> str:
            fences.append(m.group(0))
            return f"{_FENCE_PH}{len(fences) - 1}\x00"

        result = re.sub(r"```[\s\S]*?```", _save_fence, content)

        # Protect inline code
        _CODE_PH = "\x00CODE"
        codes: list[str] = []

        def _save_code(m: re.Match) -> str:
            codes.append(m.group(0))
            return f"{_CODE_PH}{len(codes) - 1}\x00"

        result = re.sub(r"`[^`\n]+`", _save_code, result)

        # Convert markdown formatting to WhatsApp syntax
        result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result)
        result = re.sub(r"__(.+?)__", r"*\1*", result)
        result = re.sub(r"~~(.+?)~~", r"~\1~", result)

        # Convert headers to bold
        result = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", result, flags=re.MULTILINE)

        # Convert links
        result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)

        # Restore protected sections
        for i, fence in enumerate(fences):
            result = result.replace(f"{_FENCE_PH}{i}\x00", fence)
        for i, code in enumerate(codes):
            result = result.replace(f"{_CODE_PH}{i}\x00", code)

        return result

    def truncate_message(self, text: str, limit: int) -> list[str]:
        """Split long messages into chunks."""
        if len(text) <= limit:
            return [text]

        chunks = []
        lines = text.split("\n")
        current = ""

        for line in lines:
            if len(current) + len(line) + 1 <= limit:
                current += ("\n" if current else "") + line
            else:
                if current:
                    chunks.append(current)
                while len(line) > limit:
                    chunks.append(line[:limit])
                    line = line[limit:]
                current = line

        if current:
            chunks.append(current)

        return chunks if chunks else [text[:limit]]

    async def connect(self) -> None:
        """Start the WhatsApp bridge."""
        if not check_whatsapp_requirements():
            logger.warning("[%s] Node.js not found. WhatsApp requires Node.js.", self.name)
            self.status.state = AdapterState.ERROR
            self.status.last_error = "Node.js not found"
            return

        bridge_path = Path(self.whatsapp_config.bridge_script) if self.whatsapp_config.bridge_script else self._DEFAULT_BRIDGE_DIR / "bridge.js"
        
        if not bridge_path.exists():
            # Try to find bridge in scripts directory
            scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
            alt_path = scripts_dir / "whatsapp-bridge" / "bridge.js"
            if alt_path.exists():
                bridge_path = alt_path
            else:
                logger.warning("[%s] Bridge script not found at %s or %s", self.name, bridge_path, alt_path)
                logger.warning("[%s] Please ensure whatsapp-bridge is installed in scripts directory", self.name)
                self.status.state = AdapterState.ERROR
                self.status.last_error = f"Bridge script not found"
                return

        logger.info("[%s] Bridge found at %s", self.name, bridge_path)

        try:
            # Ensure session directory exists
            self._session_path.mkdir(parents=True, exist_ok=True)

            # Check if bridge is already running
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://127.0.0.1:{self._bridge_port}/health",
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("status") == "connected":
                                logger.info("[%s] Using existing bridge (status: connected)", self.name)
                                self._mark_connected()
                                self._http_session = aiohttp.ClientSession()
                                self._poll_task = asyncio.create_task(self._poll_messages())
                                return
            except Exception:
                pass

            # Kill any orphaned bridge
            _kill_port_process(self._bridge_port)
            await asyncio.sleep(1)

            # Start bridge process
            whatsapp_mode = os.getenv("WHATSAPP_MODE", "self-chat")
            self._bridge_log = self._session_path.parent / "bridge.log"
            bridge_log_fh = open(self._bridge_log, "a")
            self._bridge_log_fh = bridge_log_fh

            bridge_env = os.environ.copy()
            if self.whatsapp_config.reply_prefix:
                bridge_env["WHATSAPP_REPLY_PREFIX"] = self.whatsapp_config.reply_prefix

            self._bridge_process = subprocess.Popen(
                [
                    "node",
                    str(bridge_path),
                    "--port", str(self._bridge_port),
                    "--session", str(self._session_path),
                    "--mode", whatsapp_mode,
                ],
                stdout=bridge_log_fh,
                stderr=bridge_log_fh,
                preexec_fn=None if _IS_WINDOWS else os.setsid,
                env=bridge_env,
            )

            # Wait for bridge to connect
            http_ready = False
            for attempt in range(30):
                await asyncio.sleep(1)
                if self._bridge_process.poll() is not None:
                    logger.error("[%s] Bridge process died (exit code %s)", self.name, self._bridge_process.returncode)
                    self._close_bridge_log()
                    self.status.state = AdapterState.ERROR
                    self.status.last_error = "Bridge process died"
                    return
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://127.0.0.1:{self._bridge_port}/health",
                            timeout=aiohttp.ClientTimeout(total=2)
                        ) as resp:
                            if resp.status == 200:
                                http_ready = True
                                data = await resp.json()
                                if data.get("status") == "connected":
                                    logger.info("[%s] Bridge ready (status: connected)", self.name)
                                    break
                except Exception:
                    continue
            else:
                logger.warning("[%s] Bridge HTTP server did not start in 30s", self.name)
                self._close_bridge_log()
                self.status.state = AdapterState.ERROR
                self.status.last_error = "Bridge timeout"
                return

            # Create persistent HTTP session
            self._http_session = aiohttp.ClientSession()
            self._poll_task = asyncio.create_task(self._poll_messages())
            self._mark_connected()
            logger.info("[%s] Bridge started on port %s", self.name, self._bridge_port)

        except Exception as e:
            logger.error("[%s] Failed to start bridge: %s", self.name, e)
            self.status.state = AdapterState.ERROR
            self.status.last_error = str(e)

    def _mark_connected(self) -> None:
        """Mark adapter as connected."""
        self._state = AdapterState.RUNNING
        self.status.state = AdapterState.RUNNING
        self.status.last_start_at = datetime.utcnow()

    def _close_bridge_log(self) -> None:
        """Close the bridge log file handle."""
        if self._bridge_log_fh:
            try:
                self._bridge_log_fh.close()
            except Exception:
                pass
            self._bridge_log_fh = None

    async def disconnect(self) -> None:
        """Stop the WhatsApp bridge."""
        self._state = AdapterState.STOPPING
        self.status.state = AdapterState.STOPPING

        if self._bridge_process:
            try:
                import signal
                try:
                    if _IS_WINDOWS:
                        self._bridge_process.terminate()
                    else:
                        os.killpg(os.getpgid(self._bridge_process.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    self._bridge_process.terminate()
                await asyncio.sleep(1)
                if self._bridge_process.poll() is None:
                    try:
                        if _IS_WINDOWS:
                            self._bridge_process.kill()
                        else:
                            os.killpg(os.getpgid(self._bridge_process.pid), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        self._bridge_process.kill()
            except Exception as e:
                logger.error("[%s] Error stopping bridge: %s", self.name, e)

        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

        self._bridge_process = None
        self._poll_task = None
        self._http_session = None
        self._close_bridge_log()

        self._state = AdapterState.STOPPED
        self.status.state = AdapterState.STOPPED
        self.status.last_stop_at = datetime.utcnow()
        logger.info("[%s] Disconnected", self.name)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        thread_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        media_url: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a message via WhatsApp bridge."""
        if not self._http_session or self._state != AdapterState.RUNNING:
            raise RuntimeError("Not connected")

        try:
            formatted = self.format_message(text)
            chunks = self.truncate_message(formatted, self.MAX_MESSAGE_LENGTH)

            last_message_id = None
            for chunk in chunks:
                payload: dict[str, Any] = {
                    "chatId": chat_id,
                    "message": chunk,
                }
                if reply_to and last_message_id is None:
                    payload["replyTo"] = reply_to

                async with self._http_session.post(
                    f"http://127.0.0.1:{self._bridge_port}/send",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        last_message_id = data.get("messageId")
                    else:
                        error = await resp.text()
                        raise RuntimeError(f"Send failed: {error}")

                if len(chunks) > 1:
                    await asyncio.sleep(0.3)

            return {
                "success": True,
                "platform": "whatsapp",
                "platform_message_id": last_message_id,
                "chat_id": chat_id,
            }

        except Exception as e:
            logger.error("[%s] Send error: %s", self.name, e)
            raise

    async def send_media(
        self,
        chat_id: str,
        file_path: str,
        media_type: str,
        caption: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send media file via bridge."""
        if not self._http_session or self._state != AdapterState.RUNNING:
            raise RuntimeError("Not connected")

        try:
            payload: dict[str, Any] = {
                "chatId": chat_id,
                "filePath": file_path,
                "mediaType": media_type,
            }
            if caption:
                payload["caption"] = caption

            async with self._http_session.post(
                f"http://127.0.0.1:{self._bridge_port}/send-media",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "success": True,
                        "platform": "whatsapp",
                        "platform_message_id": data.get("messageId"),
                        "chat_id": chat_id,
                    }
                else:
                    error = await resp.text()
                    raise RuntimeError(f"Send media failed: {error}")

        except Exception as e:
            logger.error("[%s] Send media error: %s", self.name, e)
            raise

    async def _poll_messages(self) -> None:
        """Poll the bridge for incoming messages."""
        while self._state == AdapterState.RUNNING:
            try:
                if not self._http_session:
                    break
                async with self._http_session.get(
                    f"http://127.0.0.1:{self._bridge_port}/messages",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        for msg_data in messages:
                            event = await self._build_message_event(msg_data)
                            if event:
                                await self.message_handler(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[%s] Poll error: %s", self.name, e)
                await asyncio.sleep(5)

            await asyncio.sleep(1)

    async def _build_message_event(self, data: dict[str, Any]) -> Optional[Message]:
        """Build a Message from bridge message data."""
        try:
            if not self._should_process_message(data):
                return None

            # Determine message type
            msg_type = MessageType.TEXT
            if data.get("hasMedia"):
                media_type = data.get("mediaType", "")
                if "image" in media_type:
                    msg_type = MessageType.MEDIA
                elif "video" in media_type:
                    msg_type = MessageType.VIDEO
                elif "audio" in media_type or "ptt" in media_type:
                    msg_type = MessageType.AUDIO
                else:
                    msg_type = MessageType.DOCUMENT

            # Build context
            is_group = data.get("isGroup", False)
            context = MessageContext(
                platform="whatsapp",
                platform_message_id=str(data.get("messageId", "")),
                chat_id=str(data.get("chatId", "")),
                chat_type=ChatType.GROUP if is_group else ChatType.DIRECT,
                sender_id=str(data.get("senderId", "")),
                sender_name=str(data.get("senderName", data.get("senderId", ""))),
                raw=data,
            )

            # Extract text
            body = data.get("body", "")
            if is_group:
                body = self._clean_bot_mention_text(body, data)

            return Message(
                type=msg_type,
                text=body,
                context=context,
                media_url=data.get("mediaUrls", [None])[0] if data.get("mediaUrls") else None,
            )

        except Exception as e:
            logger.error("[%s] Error building message: %s", self.name, e)
            return None

    def _clean_bot_mention_text(self, text: str, data: dict[str, Any]) -> str:
        """Remove bot mention from message text."""
        if not text:
            return text
        bot_ids = self._bot_ids_from_message(data)
        cleaned = text
        for bot_id in bot_ids:
            bare_id = bot_id.split("@", 1)[0]
            if bare_id:
                cleaned = re.sub(rf"@{re.escape(bare_id)}\b[,:\-]*\s*", "", cleaned)
        return cleaned.strip() or text

    async def _process_raw_message(self, raw: dict[str, Any]) -> Optional[Message]:
        """Process raw WhatsApp webhook payload."""
        return await self._build_message_event(raw)


from datetime import datetime
