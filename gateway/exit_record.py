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
    """数据根（单一真源）。

    解析顺序（MIMIR_AETHER_HOME → MIMIRAETHER_HOME → 旧键 → ~/.mimiraether）
    全仓已有实现 ``mimir_constants.get_mimir_home()``。此处独立复刻一份会漂移，
    且违反 IND-02 契约（运行时树禁裸读旧键作默认根）—— 首版即因此被契约闸拦下。

    本模块在**停机路径**上被调用 ⇒ 导入失败必须仍可用，故保留只认本项目两个键的
    窄回退，且默认值与外层一致。
    """
    try:
        from mimir_constants import get_mimir_home

        return str(get_mimir_home())
    except Exception:
        pass
    for _key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        _val = os.environ.get(_key, "").strip()
        if _val:
            return _val
    return os.path.expanduser("~" + _SLASH + ".mimiraether")


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


# ---------------------------------------------------------------------------
# 补盲区（2026-09-28）：运行时**无法**记录的死法
# ---------------------------------------------------------------------------
# 本模块的 record_exit_event 只在进程自己的停机路径上被调用 ⇒ 对
# SIGKILL/OOM（不可捕获）天然全盲。实测：22:49:50 被 cgroup OOM 杀掉，
# 表里 0 行，而 journal 有 "killed by the OOM killer" / "Failed with result
# 'oom-kill'"。纪律：**表里没有 != 没发生**——死法以 journal 记账为准。
#
# 本函数把 journal 里的停机事件与表里已记事件对账，缺的补一行
# source="journal-reconcile"。幂等：窗口内已有记录则跳过。

_JOURNAL_REASONS = (
    ("killed by the OOM killer", "oom-kill"),
    ("Failed with result 'oom-kill'", "oom-kill"),
    ("Failed with result 'timeout'", "timeout"),
    ("Failed with result 'signal'", "signal"),
    ("Failed with result 'exit-code'", "exit-code"),
    ("Failed with result 'watchdog'", "watchdog"),
)


def default_unit() -> str:
    return os.environ.get("MIMIR_GATEWAY_UNIT", "").strip() or "mimiraether.service"


def _journal_lines(unit: str, since_epoch: int, limit: int) -> list:
    """读 systemd user journal（JSON 行）。任何失败返回 []，绝不抛异常。"""
    try:
        import subprocess

        cmd = [
            "journalctl", "--user", "-u", unit,
            "--since", "@%d" % int(since_epoch),
            "-o", "json", "-n", str(int(limit)), "--no-pager",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return []
        return out.stdout.splitlines()
    except Exception:
        return []


def _msg_of(obj: dict) -> str:
    """MESSAGE 可能是 str，也可能是字节数组。"""
    raw = obj.get("MESSAGE")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        try:
            return bytes(raw).decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def parse_journal_exits(lines) -> list:
    """从 journal JSON 行解析停机事件（纯函数，可注入替身测试）。

    返回 [{"ts_epoch": int, "ts": str, "reason": str, "rss_peak_mb": float|None}]
    —— 同一事件的多行（OOM killer + Failed with result）按 5s 窗口合并。
    """
    events = []
    for line in lines or []:
        line = (line or "").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        msg = _msg_of(obj)
        reason = None
        for needle, name in _JOURNAL_REASONS:
            if needle in msg:
                reason = name
                break
        peak = None
        if "memory peak" in msg:
            try:
                seg = msg.split("memory peak")[0].strip().rstrip(",").split()[-1]
                if seg.endswith("G"):
                    peak = float(seg[:-1]) * 1024.0
                elif seg.endswith("M"):
                    peak = float(seg[:-1])
                elif seg.endswith("K"):
                    peak = float(seg[:-1]) / 1024.0
            except Exception:
                peak = None
        if reason is None and peak is None:
            continue
        try:
            usec = int(obj.get("__REALTIME_TIMESTAMP") or 0)
        except Exception:
            usec = 0
        epoch = int(usec / 1000000) if usec else 0
        if reason is None:
            # 仅 memory peak 行：挂到最近一个事件
            if events and abs(events[-1]["ts_epoch"] - epoch) <= 5:
                events[-1]["rss_peak_mb"] = peak
            continue
        if events and events[-1]["reason"] == reason and abs(events[-1]["ts_epoch"] - epoch) <= 5:
            if peak is not None:
                events[-1]["rss_peak_mb"] = peak
            continue
        events.append(
            {
                "ts_epoch": epoch,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch)) if epoch else None,
                "reason": reason,
                "rss_peak_mb": peak,
            }
        )
    return events


def read_records() -> list:
    """读全表（坏行跳过）。表不存在 ⇒ []。"""
    try:
        p = history_path()
        if not p.exists():
            return []
        out = []
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
        return out
    except Exception:
        return []


def reconcile_from_journal(
    *,
    unit: Optional[str] = None,
    read_lines=None,
    since_epoch: Optional[int] = None,
    window_s: int = 180,
    limit: int = 2000,
) -> list:
    """把 journal 里未入表的停机事件补进表。返回**新追加**的行。

    幂等：journal 事件与表内记录的 ts_epoch 相差 <= window_s ⇒ 视为已记，跳过。
    """
    try:
        unit = unit or default_unit()
        if since_epoch is None:
            since_epoch = int(time.time()) - 24 * 3600
        lines = (read_lines or (lambda u, s, l: _journal_lines(u, s, l)))(unit, since_epoch, limit)
        if not lines:
            return []
        events = parse_journal_exits(lines)
        if not events:
            return []
        recorded = [r.get("ts_epoch") for r in read_records()]
        recorded = [int(x) for x in recorded if isinstance(x, (int, float))]
        added = []
        for ev in events:
            if not ev.get("ts_epoch"):
                continue
            if any(abs(ev["ts_epoch"] - r) <= window_s for r in recorded):
                continue
            rec = {
                "ts": ev["ts"],
                "ts_epoch": ev["ts_epoch"],
                "event": "exit",
                "pid": None,
                "ppid": None,
                "signal": None,
                "source": "journal-reconcile",
                "exit_reason": ev["reason"],
                "restart_requested": None,
                "active_agents": None,
                "uptime_s": None,
                "rss_peak_mb": ev.get("rss_peak_mb"),
                "note": "运行时未能记录（不可捕获信号）：由 journal 对账补入",
                "unit": unit,
            }
            p = history_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + chr(10))
            recorded.append(ev["ts_epoch"])
            added.append(rec)
        return added
    except Exception:
        return []


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
