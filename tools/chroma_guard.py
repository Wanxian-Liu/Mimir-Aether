"""Chroma 坏库守卫（F2/④ · 2026-10-19 Mimir 全面审计）。

为什么需要它
------------
2026-10-19 坏库事故的栈是 `session_search_indexer.py:497 <- 536 <- 811`，崩在
`Collection.get` —— **进程级 SEGV**。这一条决定两件事：

1. **不能靠 try/except 兜**：SIGSEGV 不是 Python 异常，`except Exception` 接不住，
   进程直接死。所以探针必须**跑在子进程里** —— 子进程崩（returncode<0）父进程仍活着，
   才有机会降级。
2. **坏库不得删/移**（刘哥令）：所以「隔离」只能是**打标记 + 跳过**，绝不 rename/rm。
   标记文件 = `data/chroma_degraded.json`（只写标记，不动库）。

本模块只做三件事：`probe()` 判定可用性 · `mark_degraded()`/`clear_degraded()` 落标记 ·
`chroma_usable()` 给写入路径一个单一闸门。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "degrade_state_path",
    "read_degrade_state",
    "mark_degraded",
    "clear_degraded",
    "chroma_usable",
    "probe",
]

_PROBE_TIMEOUT_ENV = "MIMIR_CHROMA_PROBE_TIMEOUT_S"
_DEFAULT_TIMEOUT = 20.0


def degrade_state_path() -> Path:
    raw = (os.environ.get("MIMIR_CHROMA_DEGRADE_STATE_PATH") or "").strip()
    if raw:
        return Path(raw)
    from mimir_constants import get_mimir_home

    return Path(get_mimir_home()) / "data" / "chroma_degraded.json"


def read_degrade_state() -> Dict[str, Any]:
    try:
        with open(degrade_state_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(data: Dict[str, Any]) -> None:
    path = degrade_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def mark_degraded(reason: str, *, detail: str = "") -> Dict[str, Any]:
    """置降级标记（**先置状态再发通知**：调用方必须在通知之前调它）。"""
    rec = {
        "degraded": True,
        "reason": str(reason or "unknown"),
        "detail": str(detail)[:400],
        "since": time.time(),
        "backend": "fts5",
    }
    prev = read_degrade_state()
    if prev.get("since"):
        rec["first_since"] = prev.get("first_since") or prev.get("since")
    _write_state(rec)
    return rec


def clear_degraded(*, reason: str = "probe_ok") -> Dict[str, Any]:
    rec = {"degraded": False, "reason": reason, "since": time.time()}
    _write_state(rec)
    return rec


def chroma_usable() -> bool:
    """写入路径的单一闸门：标记为降级 => 一律不碰 chroma（防 SEGV 崩溃循环）。

    `MIMIR_CHROMA_DEGRADED=1` 可强置（演练/负控用）。
    """
    if os.environ.get("MIMIR_CHROMA_DEGRADED", "").strip() in ("1", "true", "yes"):
        return False
    return not bool(read_degrade_state().get("degraded"))


_PROBE_SRC = """
import json, sys, os
os.environ["MIMIR_CHROMA_LOCK_ROLE"] = "probe"
out = {"ok": False, "stage": "import", "lock": "ok"}
try:
    import chromadb
except Exception as e:
    out["error"] = "import: %s: %s" % (type(e).__name__, e)
    print(json.dumps(out)); sys.exit(0)
try:
    from tools.chroma_session_indexer import chroma_write_lock
except Exception as e:
    # B11（2026-10-22）：锁导入失败 ⇒ **不跑**，不再退化成 nullcontext。
    # 旧行为让探针在无锁状态下读写集合（判据上表现为 nullable=1、rc 永远红），
    # 既证明不了互斥，又可能在别的进程写入中途读到半张表。此处 fail-closed。
    out["lock"] = "unavailable"
    out["error"] = "lock_import: %s: %s" % (type(e).__name__, e)
    print(json.dumps(out)); sys.exit(0)
out["stage"] = "open"
try:
    from mimir_constants import get_mimir_chroma_dir
    root = str(get_mimir_chroma_dir())
    with chroma_write_lock():
        client = chromadb.PersistentClient(path=root)
    out["stage"] = "count"
    col = client.get_collection("session_messages")
    out["count"] = int(col.count())
    out["stage"] = "get"
    got = col.get(include=[], limit=1).get("ids") or []
    out["sample_ids"] = len(got)
    out["ok"] = True
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
print(json.dumps(out))
"""


def probe(*, timeout_s: Optional[float] = None) -> Dict[str, Any]:
    """子进程探针：只读打开 + count + get(limit=1)。

    返回 ``{ok, count, stage, error, rc, elapsed_s, segv}``。
    ``segv=True``（rc == -11）说明**进程级崩溃** —— 这是 try/except 永远接不住的那类，
    也是本次事故的形态；它本身不写标记（由调用方按策略决定），但必须出声。
    """
    raw = (os.environ.get(_PROBE_TIMEOUT_ENV) or "").strip()
    tmo = float(timeout_s if timeout_s is not None else (raw or _DEFAULT_TIMEOUT))
    t0 = time.time()
    res: Dict[str, Any] = {"ok": False, "stage": "spawn", "rc": None, "segv": False}
    try:
        cp = subprocess.run(
            [sys.executable, "-c", _PROBE_SRC],
            capture_output=True,
            text=True,
            timeout=tmo,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
    except subprocess.TimeoutExpired:
        res.update({"stage": "timeout", "error": "probe_timeout_%ss" % tmo})
        res["elapsed_s"] = round(time.time() - t0, 2)
        return res
    except Exception as exc:  # pragma: no cover
        res.update({"stage": "spawn", "error": "%s: %s" % (type(exc).__name__, exc)})
        res["elapsed_s"] = round(time.time() - t0, 2)
        return res
    res["rc"] = int(cp.returncode)
    res["elapsed_s"] = round(time.time() - t0, 2)
    if cp.returncode != 0:
        res["stage"] = "child_crash"
        res["segv"] = cp.returncode in (-11, -6, -4)
        res["error"] = ("child rc=%d segv=%s stderr=%s"
                        % (cp.returncode, res["segv"], (cp.stderr or "")[-300:]))
        return res
    line = (cp.stdout or "").strip().splitlines()[-1:] or [""]
    try:
        payload = json.loads(line[0])
    except Exception:
        res["error"] = "unparsable_probe_output: %s" % (cp.stdout or "")[-200:]
        return res
    res.update({k: payload.get(k) for k in ("ok", "count", "stage", "error")})
    res["ok"] = bool(payload.get("ok"))
    return res
