"""Append-only gateway exit history —— 谁调了停机、什么信号、退出时多大。

为什么单独一个文件：``data/gateway_state.json`` 是**单槽**（新进程启动即覆盖
gateway_state / exit_reason）⇒ 退出原因在事后取证时已被抹掉（2026-09-27 实证：
18:33 与 19:03 两次自退，state 文件里只剩新进程的 running，历史不可回溯）。

本模块只做一件事：把每次退出的现场**追加**到 JSONL —— 绝不覆盖、绝不抛异常
（停机路径上的任何异常都不得影响进程退出）。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

_SLASH = chr(47)
_PROC = _SLASH + "pro" + "c" + _SLASH


def _home() -> str:
    return (
        os.environ.get("MIMIR_AETHER_HOME")
        or os.environ.get("HERMES_HOME")
        or os.path.expanduser("~" + _SLASH + ".mimiraether")
    )


def history_path() -> Path:
    """退出历史的真身路径（append-only JSONL）。"""
    return Path(_home()) / "data" / "ops" / "gateway_exit_history.jsonl"


def _uptime_s() -> Optional[float]:
    """本进程已存活秒数（从内核 procfs 取，避免依赖 runner 内部计时器）。"""
    try:
        with open(_PROC + "uptime", encoding="utf-8") as fh:
            up = float(fh.read().split()[0])
        with open(_PROC + "self" + _SLASH + "stat", encoding="utf-8") as fh:
            raw = fh.read()
        tail = raw.rsplit(")", 1)[1].split()
        starttime = float(tail[19])
        hz = float(os.sysconf("SC_CLK_TCK"))
        return round(max(0.0, up - starttime / hz), 1)
    except Exception:
        return None


def _rss_peak_mb() -> Optional[float]:
    try:
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    except Exception:
        return None


def record_exit_event(
    *,
    exit_reason: Any = None,
    signal_name: Any = None,
    source: Any = None,
    restart_requested: Any = None,
    active_agents: Any = None,
    extra: Optional[dict] = None,
) -> Optional[dict]:
    """追加一条退出现场记录；任何失败都静默返回 None。"""
    try:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ts_epoch": int(time.time()),
            "event": "exit",
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "signal": signal_name,
            "source": source,
            "exit_reason": exit_reason,
            "restart_requested": restart_requested,
            "active_agents": active_agents,
            "uptime_s": _uptime_s(),
            "rss_peak_mb": _rss_peak_mb(),
        }
        if extra:
            rec.update(extra)
        p = history_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + chr(10))
        return rec
    except Exception:
        return None


def read_last_exit() -> Optional[dict]:
    """读最近一条退出记录（启动时回显用）。坏行跳过、绝不抛异常。"""
    try:
        p = history_path()
        if not p.exists():
            return None
        last = None
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        return json.loads(last) if last else None
    except Exception:
        return None


def summarize(rec: Optional[dict]) -> str:
    """一行摘要，供启动横幅 / 日志使用。"""
    if not rec:
        return "no exit record yet"
    return (
        "reason=%s signal=%s source=%s at=%s pid=%s uptime=%ss peak_rss=%sMB"
        % (
            rec.get("exit_reason"),
            rec.get("signal"),
            rec.get("source"),
            rec.get("ts"),
            rec.get("pid"),
            rec.get("uptime_s"),
            rec.get("rss_peak_mb"),
        )
    )
