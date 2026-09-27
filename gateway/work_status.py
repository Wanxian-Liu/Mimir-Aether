"""飞书工作状态播报（轻量·防刷屏）—— 2026-09-27 Mimir 自研。

任务来源: wiki/discussions/2026-09-27-飞书体验升级-已读表情与播报.md

设计约束（对齐任务单「教训三条」）:
  1. 走飞书主通道 —— 复用平台 adapter.send；不建新服务、不绑 Flask/端口
  2. 纯代码 hook —— 零 LLM 调用，不占推理预算
  3. 防刷屏 —— 每 run 上限 MAX_TOTAL_PER_RUN 条、最小间隔 MIN_INTERVAL 秒、
     文本去重、闲时（未开工 / 无活跃 run）不发

三钩子: 开工 🔧 → 中途 ⚙️（≤MAX_STEP_PER_RUN 条）→ 完工 ✅（失败/取消 ⚠️）。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

START_EMOJI = "🔧"
STEP_EMOJI = "⚙️"
DONE_EMOJI = "✅"
FAIL_EMOJI = "⚠️"

MAX_TOTAL_PER_RUN = 4     # 1 开工 + 2 中途 + 1 完工（验收读数 4：连续任务 <=4 条）
MAX_STEP_PER_RUN = 2
MIN_INTERVAL = 2.0        # 秒；两条播报之间的最小间隔
TASK_SUMMARY_MAX = 40
REPLY_SUMMARY_MAX = 60
RUN_TTL = 1800.0          # 30 min；僵尸 run 清理

def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")

def summarize(text: Any, limit: int = TASK_SUMMARY_MAX) -> str:
    """取首行、压空白、截断。"""
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    line = s.splitlines()[0]
    line = " ".join(line.split())
    if len(line) > limit:
        line = line[: max(1, limit - 1)] + "…"
    return line

class WorkStatusBroadcaster:
    """按 run 记录状态并播报；所有发送失败都只记日志，绝不抛给调用方。"""

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._runs: Dict[str, dict] = {}
        self._replies: Dict[str, str] = {}
        self._enabled = _env_flag("MIMIR_WORK_STATUS_BROADCAST", True) if enabled is None else bool(enabled)
        self.sent_log: List[dict] = []   # 自证用：本进程真实发出的播报

    # -- 开关 --
    def enabled_for(self, platform: Any) -> bool:
        if not self._enabled:
            return False
        name = str(getattr(platform, "value", platform) or "").strip().lower()
        return name == "feishu"

    @staticmethod
    def _key(platform: Any, chat_id: str) -> str:
        name = str(getattr(platform, "value", platform) or "").strip().lower()
        return f"{name}:{chat_id}"

    # -- 出站素材（供「完工：结果一句」） --
    def record_reply(self, chat_id: str, content: Any) -> None:
        s = str(content or "").strip()
        if not s:
            return
        if s[:1] in (START_EMOJI, STEP_EMOJI, DONE_EMOJI, FAIL_EMOJI):
            return   # 状态播报自身不入素材
        self._replies[str(chat_id)] = summarize(s, REPLY_SUMMARY_MAX)

    # -- 内部 --
    def _prune(self, now: float) -> None:
        stale = [k for k, st in self._runs.items() if now - st.get("started", now) > RUN_TTL]
        for k in stale:
            self._runs.pop(k, None)

    def _allow(self, st: dict, now: float, *, is_step: bool = False) -> bool:
        if st["sent"] >= MAX_TOTAL_PER_RUN:
            return False
        if is_step and st["steps"] >= MAX_STEP_PER_RUN:
            return False
        if now - st["last_sent_at"] < MIN_INTERVAL:
            return False
        return True

    async def _emit(self, adapter: Any, chat_id: str, thread_id: Optional[str], st: dict, msg: str) -> bool:
        if msg == st.get("last_msg"):
            return False
        meta = {"thread_id": thread_id} if thread_id else None
        ok = False
        try:
            res = await adapter.send(chat_id=chat_id, content=msg, metadata=meta)
            ok = bool(getattr(res, "success", False))
        except Exception as exc:  # 兜底：播报失败绝不影响主流程
            logger.warning("[work_status] send failed: %s", exc)
        st["sent"] += 1
        st["last_sent_at"] = time.monotonic()
        st["last_msg"] = msg
        self.sent_log.append({"key": st.get("key", ""), "msg": msg, "ok": ok})
        logger.info("[work_status] broadcast(%s) ok=%s: %s", st.get("key", ""), ok, msg)
        return ok

    # -- 三钩子 --
    async def start(self, adapter: Any, chat_id: str, thread_id: Optional[str] = None, text: Any = "") -> bool:
        now = time.monotonic()
        self._prune(now)
        key = self._key(getattr(adapter, "platform", None) or "feishu", chat_id)
        task = summarize(text, TASK_SUMMARY_MAX)
        st = {"key": key, "started": now, "sent": 0, "steps": 0,
              "last_sent_at": 0.0, "last_msg": "", "task": task}
        self._runs[key] = st
        self._replies.pop(str(chat_id), None)
        msg = f"{START_EMOJI} 开工：{task}" if task else f"{START_EMOJI} 开工"
        return await self._emit(adapter, chat_id, thread_id, st, msg)

    async def step(self, adapter: Any, chat_id: str, thread_id: Optional[str], tool_names: Sequence[str]) -> bool:
        key = self._key(getattr(adapter, "platform", None) or "feishu", chat_id)
        st = self._runs.get(key)
        if st is None:
            return False   # 闲时不发：没有活跃 run 就不播报
        now = time.monotonic()
        if not self._allow(st, now, is_step=True):
            return False
        names = [str(n) for n in (tool_names or []) if n]
        if not names:
            return False
        label = summarize(", ".join(names), TASK_SUMMARY_MAX)
        st["steps"] += 1
        return await self._emit(adapter, chat_id, thread_id, st, f"{STEP_EMOJI} {label}")

    async def finish(self, adapter: Any, chat_id: str, thread_id: Optional[str] = None, outcome: Any = None) -> bool:
        key = self._key(getattr(adapter, "platform", None) or "feishu", chat_id)
        st = self._runs.pop(key, None)   # run 结束即清（闲时不发）
        if st is None or st["sent"] == 0:
            return False
        ok_outcome = str(getattr(outcome, "value", outcome) or "success").lower() == "success"
        reply = self._replies.pop(str(chat_id), "")
        now = time.monotonic()
        if not self._allow(st, now):
            self.sent_log.append({"key": key, "msg": "(finish dropped: cap/throttle)", "ok": False})
            return False
        if ok_outcome:
            msg = f"{DONE_EMOJI} 完工：{reply}" if reply else f"{DONE_EMOJI} 完工"
        else:
            msg = f"{FAIL_EMOJI} 中断：{reply}" if reply else f"{FAIL_EMOJI} 中断"
        return await self._emit(adapter, chat_id, thread_id, st, msg)

_BROADCASTER: Optional[WorkStatusBroadcaster] = None

def get_broadcaster() -> WorkStatusBroadcaster:
    global _BROADCASTER
    if _BROADCASTER is None:
        _BROADCASTER = WorkStatusBroadcaster()
    return _BROADCASTER
