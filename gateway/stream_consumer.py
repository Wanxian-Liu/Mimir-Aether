"""
Stream consumer — handles progressive/editable streaming responses.

# TODO-自研: 流式消息消费，可适配更多流式协议与平台特性
"""

import asyncio
import queue
import re
import time
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


# ── Queue sentinel values ────────────────────────────────────────────────
_DONE = object()
_NEW_SEGMENT = object()
_COMMENTARY = object()


# TODO-自研: StreamConsumerConfig 可扩展更多流式配置选项
class StreamConsumerConfig:
    """Configuration for the stream consumer."""

    def __init__(
        self,
        cursor: str = "▉",
        edit_interval: float = 0.8,
        buffer_threshold: int = 2000,
    ):
        self.cursor = cursor
        self.edit_interval = edit_interval
        self.buffer_threshold = buffer_threshold


class GatewayStreamConsumer:
    """Consumes a streaming delta sequence and edits a single platform message.

    Handles:
    - Progressive edits (cursor-based streaming)
    - Think-block filtering (strips <think> tags)
    - Overflow splitting (splits oversized messages into chunks)
    - Flood-control adaptive backoff
    - Fallback final-send when progressive editing breaks

    # TODO-自研: 可适配更多流式协议，增加更多平台特定处理
    """

    _MAX_FLOOD_STRIKES = 3

    _OPEN_THINK_TAGS = (
        "<think>", "<reasoning>",
        "<REASONING_SCRATCHPAD>", "<THINKING>", "<thought>",
    )
    _CLOSE_THINK_TAGS = (
        "</think>", "</reasoning>",
        "</REASONING_SCRATCHPAD>", "</THINKING>", "</thinking>", "</thought>",
    )

    def __init__(
        self,
        adapter: Any,
        chat_id: str,
        config: Optional[StreamConsumerConfig] = None,
        metadata: Optional[dict] = None,
    ):
        self.adapter = adapter
        self.chat_id = chat_id
        self.cfg = config or StreamConsumerConfig()
        self.metadata = metadata
        self._queue: queue.Queue = queue.Queue()
        self._accumulated = ""
        self._message_id: Optional[str] = None
        self._already_sent = False
        self._edit_supported = True
        self._last_edit_time = 0.0
        self._last_sent_text = ""
        self._fallback_final_send = False
        self._fallback_prefix = ""
        self._flood_strikes = 0
        self._current_edit_interval = self.cfg.edit_interval
        self._final_response_sent = False

        # Think-block filter state
        self._in_think_block = False
        self._think_buffer = ""

    @property
    def already_sent(self) -> bool:
        return self._already_sent

    @property
    def final_response_sent(self) -> bool:
        return self._final_response_sent

    def on_segment_break(self) -> None:
        self._queue.put(_NEW_SEGMENT)

    def on_commentary(self, text: str) -> None:
        if text:
            self._queue.put((_COMMENTARY, text))

    def _reset_segment_state(self, *, preserve_no_edit: bool = False) -> None:
        if preserve_no_edit and self._message_id == "__no_edit__":
            return
        self._message_id = None
        self._accumulated = ""
        self._last_sent_text = ""
        self._fallback_final_send = False
        self._fallback_prefix = ""

    def on_delta(self, text: str) -> None:
        if text:
            self._queue.put(text)
        elif text is None:
            self.on_segment_break()

    def finish(self) -> None:
        self._queue.put(_DONE)

    # ── Think-block filtering ────────────────────────────────────────
    # Models like MiniMax emit inline <think>... blocks in their
    # content.  The stream consumer strips these so users never see
    # raw reasoning tags.

    def _filter_and_accumulate(self, text: str) -> None:
        buf = self._think_buffer + text
        self._think_buffer = ""

        while buf:
            if self._in_think_block:
                best_idx = -1
                best_len = 0
                for tag in self._CLOSE_THINK_TAGS:
                    idx = buf.find(tag)
                    if idx != -1 and (best_idx == -1 or idx < best_idx):
                        best_idx = idx
                        best_len = len(tag)

                if best_len:
                    self._in_think_block = False
                    buf = buf[best_idx + best_len:]
                else:
                    max_tag = max(len(t) for t in self._CLOSE_THINK_TAGS)
                    self._think_buffer = buf[-max_tag:] if len(buf) > max_tag else buf
                    return
            else:
                best_idx = -1
                best_len = 0
                for tag in self._OPEN_THINK_TAGS:
                    search_start = 0
                    while True:
                        idx = buf.find(tag, search_start)
                        if idx == -1:
                            break
                        if idx == 0:
                            is_boundary = not self._accumulated or self._accumulated.endswith("\n")
                        else:
                            preceding = buf[:idx]
                            last_nl = preceding.rfind("\n")
                            if last_nl == -1:
                                is_boundary = (not self._accumulated or self._accumulated.endswith("\n")) and preceding.strip() == ""
                            else:
                                is_boundary = preceding[last_nl + 1:].strip() == ""

                        if is_boundary and (best_idx == -1 or idx < best_idx):
                            best_idx = idx
                            best_len = len(tag)
                            break
                        search_start = idx + 1

                if best_len:
                    self._accumulated += buf[:best_idx]
                    self._in_think_block = True
                    buf = buf[best_idx + best_len:]
                else:
                    held_back = 0
                    for tag in self._OPEN_THINK_TAGS:
                        for i in range(1, len(tag)):
                            if buf.endswith(tag[:i]) and i > held_back:
                                held_back = i
                    if held_back:
                        self._accumulated += buf[:-held_back]
                        self._think_buffer = buf[-held_back:]
                    else:
                        self._accumulated += buf
                    return

    def _flush_think_buffer(self) -> None:
        if self._think_buffer and not self._in_think_block:
            self._accumulated += self._think_buffer
            self._think_buffer = ""

    # TODO-自研: run() 方法为核心流式消费逻辑，可适配更多流式协议
    async def run(self) -> None:
        _raw_limit = getattr(self.adapter, "MAX_MESSAGE_LENGTH", 4096)
        _safe_limit = max(500, _raw_limit - len(self.cfg.cursor) - 100)

        try:
            while True:
                got_done = False
                got_segment_break = False
                commentary_text = None
                while True:
                    try:
                        item = self._queue.get_nowait()
                        if item is _DONE:
                            got_done = True
                            break
                        if item is _NEW_SEGMENT:
                            got_segment_break = True
                            break
                        if isinstance(item, tuple) and len(item) == 2 and item[0] is _COMMENTARY:
                            commentary_text = item[1]
                            break
                        self._filter_and_accumulate(item)
                    except queue.Empty:
                        break

                if got_done:
                    self._flush_think_buffer()

                now = time.monotonic()
                elapsed = now - self._last_edit_time
                should_edit = (
                    got_done
                    or got_segment_break
                    or commentary_text is not None
                    or (elapsed >= self._current_edit_interval and self._accumulated)
                    or len(self._accumulated) >= self.cfg.buffer_threshold
                )

                current_update_visible = False
                if should_edit and self._accumulated:
                    if (
                        len(self._accumulated) > _safe_limit
                        and self._message_id is None
                    ):
                        chunks = self.adapter.truncate_message(
                            self._accumulated, _safe_limit
                        )
                        for chunk in chunks:
                            await self._send_new_chunk(chunk, self._message_id)
                        self._accumulated = ""
                        self._last_sent_text = ""
                        self._last_edit_time = time.monotonic()
                        if got_done:
                            self._final_response_sent = self._already_sent
                            return
                        if got_segment_break:
                            self._message_id = None
                            self._fallback_final_send = False
                            self._fallback_prefix = ""
                        continue

                    while (
                        len(self._accumulated) > _safe_limit
                        and self._message_id is not None
                        and self._edit_supported
                    ):
                        split_at = self._accumulated.rfind("\n", 0, _safe_limit)
                        if split_at < _safe_limit // 2:
                            split_at = _safe_limit
                        chunk = self._accumulated[:split_at]
                        ok = await self._send_or_edit(chunk)
                        if self._fallback_final_send or not ok:
                            break
                        self._accumulated = self._accumulated[split_at:].lstrip("\n")
                        self._message_id = None
                        self._last_sent_text = ""

                    display_text = self._accumulated
                    if not got_done and not got_segment_break and commentary_text is None:
                        display_text += self.cfg.cursor

                    current_update_visible = await self._send_or_edit(display_text)
                    self._last_edit_time = time.monotonic()

                if got_done:
                    if self._accumulated:
                        if self._fallback_final_send:
                            await self._send_fallback_final(self._accumulated)
                        elif current_update_visible:
                            self._final_response_sent = True
                        elif self._message_id:
                            self._final_response_sent = await self._send_or_edit(self._accumulated)
                        elif not self._already_sent:
                            self._final_response_sent = await self._send_or_edit(self._accumulated)
                    return

                if commentary_text is not None:
                    self._reset_segment_state()
                    await self._send_commentary(commentary_text)
                    self._last_edit_time = time.monotonic()
                    self._reset_segment_state()

                if got_segment_break:
                    self._reset_segment_state(preserve_no_edit=True)

                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            if self._accumulated and self._message_id:
                try:
                    await self._send_or_edit(self._accumulated)
                except Exception:
                    pass
            if self._already_sent:
                self._final_response_sent = True
        except Exception as e:
            logger.error("Stream consumer error: %s", e)

    _MEDIA_RE = re.compile(r'''[`"']?MEDIA:\s*\S+[`"']?''')

    @staticmethod
    def _clean_for_display(text: str) -> str:
        if "MEDIA:" not in text and "[[audio_as_voice]]" not in text:
            return text
        cleaned = text.replace("[[audio_as_voice]]", "")
        cleaned = GatewayStreamConsumer._MEDIA_RE.sub("", cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.rstrip()

    async def _send_new_chunk(self, text: str, reply_to_id: Optional[str]) -> Optional[str]:
        text = self._clean_for_display(text)
        if not text.strip():
            return reply_to_id
        try:
            meta = dict(self.metadata) if self.metadata else {}
            result = await self.adapter.send(
                chat_id=self.chat_id,
                content=text,
                reply_to=reply_to_id,
                metadata=meta,
            )
            if result.success and result.message_id:
                self._message_id = str(result.message_id)
                self._already_sent = True
                self._last_sent_text = text
                return str(result.message_id)
            else:
                self._edit_supported = False
                return reply_to_id
        except Exception as e:
            logger.error("Stream send chunk error: %s", e)
            return reply_to_id

    def _visible_prefix(self) -> str:
        prefix = self._last_sent_text or ""
        if self.cfg.cursor and prefix.endswith(self.cfg.cursor):
            prefix = prefix[:-len(self.cfg.cursor)]
        return self._clean_for_display(prefix)

    def _continuation_text(self, final_text: str) -> str:
        prefix = self._fallback_prefix or self._visible_prefix()
        if prefix and final_text.startswith(prefix):
            return final_text[len(prefix):].lstrip()
        return final_text

    @staticmethod
    def _split_text_chunks(text: str, limit: int) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks: list[str] = []
        remaining = text
        while len(remaining) > limit:
            split_at = remaining.rfind("\n", 0, limit)
            if split_at < limit // 2:
                split_at = limit
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")
        if remaining:
            chunks.append(remaining)
        return chunks

    async def _send_fallback_final(self, text: str) -> None:
        final_text = self._clean_for_display(text)
        continuation = self._continuation_text(final_text)
        self._fallback_final_send = False
        if not continuation.strip():
            self._already_sent = True
            self._final_response_sent = True
            return

        raw_limit = getattr(self.adapter, "MAX_MESSAGE_LENGTH", 4096)
        safe_limit = max(500, raw_limit - 100)
        chunks = self._split_text_chunks(continuation, safe_limit)

        last_message_id: Optional[str] = None
        last_successful_chunk = ""
        sent_any_chunk = False
        for chunk in chunks:
            result = None
            for attempt in range(2):
                result = await self.adapter.send(
                    chat_id=self.chat_id,
                    content=chunk,
                    metadata=self.metadata,
                )
                if result.success:
                    break
                if attempt == 0 and self._is_flood_error(result):
                    logger.debug("Flood control on fallback send, retrying in 3s")
                    await asyncio.sleep(3.0)
                else:
                    break

            if not result or not result.success:
                if sent_any_chunk:
                    self._already_sent = True
                    self._final_response_sent = True
                    self._message_id = last_message_id
                    self._last_sent_text = last_successful_chunk
                    self._fallback_prefix = ""
                    return
                self._already_sent = False
                self._message_id = None
                self._last_sent_text = ""
                self._fallback_prefix = ""
                return
            sent_any_chunk = True
            last_successful_chunk = chunk
            last_message_id = result.message_id or last_message_id

        self._message_id = last_message_id
        self._already_sent = True
        self._final_response_sent = True
        self._last_sent_text = chunks[-1]
        self._fallback_prefix = ""

    def _is_flood_error(self, result) -> bool:
        err = getattr(result, "error", "") or ""
        err_lower = err.lower()
        return "flood" in err_lower or "retry after" in err_lower or "rate" in err_lower

    async def _try_strip_cursor(self) -> None:
        if not self._message_id or self._message_id == "__no_edit__":
            return
        prefix = self._visible_prefix()
        if not prefix or not prefix.strip():
            return
        try:
            await self.adapter.edit_message(
                chat_id=self.chat_id,
                message_id=self._message_id,
                content=prefix,
            )
            self._last_sent_text = prefix
        except Exception:
            pass

    async def _send_commentary(self, text: str) -> bool:
        text = self._clean_for_display(text)
        if not text.strip():
            return False
        try:
            result = await self.adapter.send(
                chat_id=self.chat_id,
                content=text,
                metadata=self.metadata,
            )
            if result.success:
                self._already_sent = True
                return True
        except Exception as e:
            logger.error("Commentary send error: %s", e)
        return False

    async def _send_or_edit(self, text: str) -> bool:
        text = self._clean_for_display(text)
        visible_without_cursor = text
        if self.cfg.cursor:
            visible_without_cursor = visible_without_cursor.replace(self.cfg.cursor, "")
        if not visible_without_cursor.strip():
            return True
        if not text.strip():
            return True
        try:
            if self._message_id is not None:
                if self._edit_supported:
                    if text == self._last_sent_text:
                        return True
                    result = await self.adapter.edit_message(
                        chat_id=self.chat_id,
                        message_id=self._message_id,
                        content=text,
                    )
                    if result.success:
                        self._already_sent = True
                        self._last_sent_text = text
                        self._flood_strikes = 0
                        return True
                    else:
                        if self._is_flood_error(result):
                            self._flood_strikes += 1
                            self._current_edit_interval = min(
                                self._current_edit_interval * 2, 10.0,
                            )
                            logger.debug(
                                "Flood control on edit (strike %d/%d), backoff interval → %.1fs",
                                self._flood_strikes,
                                self._MAX_FLOOD_STRIKES,
                                self._current_edit_interval,
                            )
                            if self._flood_strikes < self._MAX_FLOOD_STRIKES:
                                self._last_edit_time = time.monotonic()
                                return False

                        logger.debug("Edit failed (strikes=%d), entering fallback mode", self._flood_strikes)
                        self._fallback_prefix = self._visible_prefix()
                        self._fallback_final_send = True
                        self._edit_supported = False
                        self._already_sent = True
                        await self._try_strip_cursor()
                        return False
                else:
                    return False
            else:
                result = await self.adapter.send(
                    chat_id=self.chat_id,
                    content=text,
                    metadata=self.metadata,
                )
                if result.success:
                    if result.message_id:
                        self._message_id = result.message_id
                    else:
                        self._edit_supported = False
                    self._already_sent = True
                    self._last_sent_text = text
                    if not result.message_id:
                        self._fallback_prefix = self._visible_prefix()
                        self._fallback_final_send = True
                        self._message_id = "__no_edit__"
                    return True
                else:
                    self._edit_supported = False
                    return False
        except Exception as e:
            logger.error("Stream send/edit error: %s", e)
            return False
