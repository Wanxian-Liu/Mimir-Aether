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
    "classify",
    "startup_action",
    "probe",
]

_PROBE_TIMEOUT_ENV = "MIMIR_CHROMA_PROBE_TIMEOUT_S"
# 探针在子进程里**要先等写锁**才能开库，而写锁的默认预算是 60s（见
# chroma_session_indexer.DEFAULT_WRITE_LOCK_TIMEOUT_S）。探针预算必须大于锁预算：
# 20s < 60s 时，一次「忙但健康」的长写就会被判成「库坏了」——而且（第 3 批之前）
# 一旦置了降级标记就再也不撤，等于用一次繁忙把索引永久踢到 FTS5。
# 90s = 60s 等锁 + 30s 开库/count/get 余量。
_DEFAULT_TIMEOUT = 90.0


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
    """撤降级标记（第 3 批之前**零调用方** ⇒ 一次误判就是永久 FTS5）。

    只有「探针真的通过」才该走到这里。保留上一段的 reason/since 与停摆时长：
    降级窗口本身就是证据，撤了标记不该把事故一起抹掉。
    """
    prev = read_degrade_state()
    rec: Dict[str, Any] = {"degraded": False, "reason": reason, "since": time.time()}
    if prev.get("degraded"):
        rec["prev_reason"] = prev.get("reason")
        rec["prev_since"] = prev.get("since")
        try:
            rec["outage_s"] = round(rec["since"] - float(prev["since"]), 1)
        except (KeyError, TypeError, ValueError):
            pass
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
    # 第 3 批：**阶段必须自成一档**。之前锁导入失败后 stage 仍是 "import"，与
    # 「chromadb 本身导不进来」逐字同形 ⇒ 看读数的人分不清「代码/部署坏了」和
    # 「库/环境坏了」，两种故障的修法完全不同。故先置 stage 再导入。
    out["stage"] = "lock_import"
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


def classify(res: Dict[str, Any]) -> str:
    """把探针读数折成一个可判定的结论。

    为什么单独成函数：这个映射决定「要不要把索引踢到 FTS5」，必须能在不起网关的
    情况下逐格验证（tests/tools/test_chroma_guard_policy.py）。第 3 批之前这段逻辑
    写在 gateway/run.py 里，等价于「不是 ok 就降级」——`inconclusive` 与真故障同权。

    ok / segv / store_error / chroma_import / lock_missing / inconclusive
    """
    if res.get("ok"):
        return "ok"
    if res.get("segv"):
        return "segv"
    stage = res.get("stage")
    if stage in ("timeout", "spawn", "child_crash"):
        # 超时 ≠ 坏库：探针要等写锁，忙只是忙。子进程非信号死亡（如 OOM -9）同样
        # 不能证明库坏了——**没有证据就不下结论**。
        return "inconclusive"
    if stage == "import":
        return "chroma_import"
    if stage == "lock_import":
        return "lock_missing"
    if stage in ("open", "count", "get"):
        return "store_error"
    return "inconclusive"


# 分类 ⇒ 降级原因。**不在这张表里的分类一律不写标记**（inconclusive 没有发言权）。
_MARK_REASONS = {
    "segv": "startup_probe_segv",
    "store_error": "startup_probe_failed",
    "chroma_import": "startup_chroma_import_failed",
    # 锁模块导不进来：不能无锁写（B11 fail-closed），但库本身可能是好的——
    # 所以原因单独一档，修法是部署/代码，不是修库。
    "lock_missing": "startup_lock_unavailable",
}


def startup_action(res: Dict[str, Any]) -> Optional[str]:
    """启动探针 ⇒ 该不该置降级。返回 reason；返回 None = 不下结论、不改状态。"""
    return _MARK_REASONS.get(res.get("classification") or classify(res))


def _finish(res: Dict[str, Any]) -> Dict[str, Any]:
    res["classification"] = classify(res)
    return res


def probe(*, timeout_s: Optional[float] = None) -> Dict[str, Any]:
    """子进程探针：只读打开 + count + get(limit=1)。

    返回 ``{ok, count, stage, lock, error, rc, elapsed_s, segv, classification}``。
    ``segv=True``（rc == -11）说明**进程级崩溃** —— 这是 try/except 永远接不住的那类，
    也是本次事故的形态；它本身不写标记（由调用方按策略决定），但必须出声。
    ``lock``（第 3 批补回）：子进程报的锁状态（``ok`` / ``unavailable``）。之前只
    透传 ok/count/stage/error，`_PROBE_SRC` 写的 ``lock`` 被静默丢掉 ⇒ 读不出「这次
    失败是不是因为没锁」。
    """
    raw = (os.environ.get(_PROBE_TIMEOUT_ENV) or "").strip()
    tmo = float(timeout_s if timeout_s is not None else (raw or _DEFAULT_TIMEOUT))
    t0 = time.time()
    res: Dict[str, Any] = {"ok": False, "stage": "spawn", "rc": None, "segv": False,
                           "lock": "unknown"}
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
        return _finish(res)
    except Exception as exc:  # pragma: no cover
        res.update({"stage": "spawn", "error": "%s: %s" % (type(exc).__name__, exc)})
        res["elapsed_s"] = round(time.time() - t0, 2)
        return _finish(res)
    res["rc"] = int(cp.returncode)
    res["elapsed_s"] = round(time.time() - t0, 2)
    if cp.returncode != 0:
        res["stage"] = "child_crash"
        res["segv"] = cp.returncode in (-11, -6, -4)
        res["error"] = ("child rc=%d segv=%s stderr=%s"
                        % (cp.returncode, res["segv"], (cp.stderr or "")[-300:]))
        return _finish(res)
    line = (cp.stdout or "").strip().splitlines()[-1:] or [""]
    try:
        payload = json.loads(line[0])
    except Exception:
        res["error"] = "unparsable_probe_output: %s" % (cp.stdout or "")[-200:]
        return _finish(res)
    # 读数面必须键位稳定（消费方按 key 取，缺键就是崩）：这几个键一律在，哪怕是 None。
    for k in ("ok", "count", "stage", "error", "sample_ids"):
        res[k] = payload.get(k)
    if payload.get("lock") is not None:
        res["lock"] = payload["lock"]   # 子女没报就保留 unknown，别写成 None
    res["ok"] = bool(payload.get("ok"))
    return _finish(res)
