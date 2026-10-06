"""F-1 退出看门狗 —— 「停机路径跑完 ≠ 进程退出」的兜底闸。

背景（F-1 · 2026-10-07 取证）：
    systemd `TimeoutStopSec=30` 内进程没退出 ⇒ systemd 发 SIGKILL 并记
    `Failed with result 'timeout'` ⇒ 拉起被记为 failure。
    实证（2026-10-06 18:07）：停机路径 **7 ms 就跑完**（gateway.log
    `.373 Stopping gateway...` → `.380 Gateway stopped`），但进程活到 18:07:30
    才被 SIGKILL ⇒ **卡点不在停机逻辑，在停机之后的收尾**：
    `asyncio.run()` 收尾会 join 默认 executor 的工作线程（CPython 上限 300s），
    残留 task / 线程同样无界 —— 谁卡住不确定，但**必须给整条尾链一个上限**。

本模块的职责（唯一）：给整个停机尾链一个**硬上限**，到点就
    ① 落线程栈现场（谁卡住，下次能点名）② 出声（ERROR 日志）
    ③ 立刻退出（`os._exit`，绕过无界的 atexit/线程 join），退出码沿用本来的意图
       （例如 service restart 的 75），让 systemd 看到 **code=exited** 而不是 SIGKILL。

设计取舍：
    * 上限默认 20s（< systemd 30s，留 10s 余量），env `MIMIR_EXIT_WATCHDOG_SECS` 可调，
      并夹在 [1, 29]（永远不许 ≥ systemd 的 30s —— 那等于没装）。
    * 只 arm 一次（单写窗口）；重复 arm 返回既有线程。
    * 纯函数（`exit_watchdog_seconds` / `drain_budget_seconds`）与副作用（`arm_*`）分离，
      便于无副作用回归测试。
"""
from __future__ import annotations

import os
import threading
import time
import traceback
from pathlib import Path

DEFAULT_EXIT_WATCHDOG_S = 20.0
MAX_EXIT_WATCHDOG_S = 29.0          # 必须 < systemd TimeoutStopSec(30)
MIN_EXIT_WATCHDOG_S = 1.0
DEFAULT_DRAIN_MARGIN_S = 8.0        # 留给 adapter 断开 / 清理 / 解释器收尾
_ENV = "MIMIR_EXIT_WATCHDOG_SECS"

_lock = threading.Lock()
_state: dict = {"thread": None, "seconds": None, "trigger": None, "fired": 0}


def exit_watchdog_seconds(raw: object = None) -> float:
    """解析看门狗上限（秒）。env 优先；非法值回落默认；结果夹在 [1, 29]。"""
    if raw is None:
        raw = os.getenv(_ENV, "")
    text = str(raw or "").strip()
    try:
        value = float(text) if text else DEFAULT_EXIT_WATCHDOG_S
    except (TypeError, ValueError):
        return DEFAULT_EXIT_WATCHDOG_S
    if value != value:  # NaN
        return DEFAULT_EXIT_WATCHDOG_S
    return max(MIN_EXIT_WATCHDOG_S, min(MAX_EXIT_WATCHDOG_S, value))


def drain_budget_seconds(drain_timeout: float, watchdog: float | None = None,
                         margin: float = DEFAULT_DRAIN_MARGIN_S) -> float:
    """把 drain 上限夹进看门狗预算内（drain 不许吃掉整条尾链）。"""
    wd = exit_watchdog_seconds(watchdog if watchdog is not None else None)
    try:
        drain = float(drain_timeout)
    except (TypeError, ValueError):
        return max(0.0, wd - margin)
    if drain != drain:
        drain = wd - margin
    return max(0.0, min(drain, wd - margin))


def _dump_threads(home: object, trigger: str) -> str:
    """落线程栈现场（best-effort，任何失败都不得影响退出）。"""
    try:
        lines = ["# F-1 exit watchdog fired: trigger=%s" % trigger, ""]
        frames = None
        try:
            import sys as _sys
            frames = _sys._current_frames()
        except Exception:
            frames = None
        for th in threading.enumerate():
            lines.append("== thread %s daemon=%s alive=%s" % (th.name, th.daemon, th.is_alive()))
            frame = (frames or {}).get(th.ident)
            if frame is not None:
                lines.extend(traceback.format_stack(frame))
            lines.append("")
        text = "\n".join(lines)
        base = Path(home) if home else Path("/tmp")
        out_dir = base / "logs" / "stack-dumps"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / ("exit-watchdog-%d.log" % int(time.time()))
            path.write_text(text, encoding="utf-8")
            return str(path)
        except Exception:
            return ""
    except Exception:
        return ""


def _flush_logging() -> None:
    try:
        import sys as _sys
        for stream in (_sys.stdout, _sys.stderr):
            try:
                stream.flush()
            except Exception:
                pass
        import logging
        logging.shutdown()
    except Exception:
        pass


def arm_exit_watchdog(trigger: str, seconds: float | None = None, home: object = None,
                      logger=None, exit_code_provider=None) -> threading.Thread | None:
    """武装退出看门狗（单写窗口：已武装则直接返回既有线程）。"""
    with _lock:
        existing = _state.get("thread")
        if existing is not None and existing.is_alive():
            return existing
        budget = exit_watchdog_seconds(seconds)
        holder: dict = {}

        def _run() -> None:
            time.sleep(budget)
            _state["fired"] = int(_state.get("fired", 0)) + 1
            code = 0
            if callable(exit_code_provider):
                try:
                    value = exit_code_provider()
                    if value is not None:
                        code = int(value)
                except Exception:
                    code = 0
            dump_path = _dump_threads(home, trigger)
            try:
                if logger is not None:
                    logger.error(
                        "F1_EXIT_WATCHDOG_FIRED trigger=%s after=%.1fs threads=%d "
                        "exit_code=%s stacks=%s — forced exit before systemd TimeoutStopSec",
                        trigger, budget, threading.active_count(), code, dump_path or "n/a",
                    )
            except Exception:
                pass
            _flush_logging()
            os._exit(code)

        thread = threading.Thread(target=_run, name="f1-exit-watchdog", daemon=True)
        holder["t"] = thread
        _state.update({"thread": thread, "seconds": budget, "trigger": trigger})
        thread.start()
        return thread


def status() -> dict:
    """可观测性：当前看门狗状态（审计/回归用）。"""
    with _lock:
        thread = _state.get("thread")
        return {
            "armed": bool(thread is not None and thread.is_alive()),
            "seconds": _state.get("seconds"),
            "trigger": _state.get("trigger"),
            "fired": int(_state.get("fired", 0)),
            "default_seconds": DEFAULT_EXIT_WATCHDOG_S,
        }


def _reset_for_tests() -> None:
    with _lock:
        _state.update({"thread": None, "seconds": None, "trigger": None, "fired": 0})
