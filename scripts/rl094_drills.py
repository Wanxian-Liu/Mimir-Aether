#!/usr/bin/env python3
"""RL-20261020-094 收尾演练：D11 抽样读回 / D14 收敛 / D3 双源超时。

三个子命令都用真实代码路径，不是 mock：
  d11  生产集合写一条金丝雀 → 按 doc id 读回 → 逐字段比对 → 删除（净 0）
  d14  同一次往返当收敛演练：写后 embeddings +1（drift=+1）→ 删后回基线（drift=0）
  d3   隔离 HOME：A 持锁 3s，B 预算 0.2s ⇒ 账本记 timeout=1 且失败计数=1（两源）

用法：
  MIMIR_CHROMA_INCREMENTAL=1 MIMIR_EMBED_MODEL=$HOME/models/bge-m3 \
    .venv/bin/python scripts/rl094_drills.py d11|d14
  MIMIR_AETHER_HOME=/tmp/rl094-d3 .venv/bin/python scripts/rl094_drills.py d3

退出码：0 全过 / 2 有断言失败（逐条打印 PASS/FAIL）
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SID = "rl094-canary"


def _counts() -> int:
    from mimir_constants import get_mimir_chroma_dir

    db = Path(get_mimir_chroma_dir()) / "chroma.sqlite3"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    try:
        return int(con.execute("select count(*) from embeddings").fetchone()[0])
    finally:
        con.close()


def _say(name: str, ok: bool, detail: str = "") -> bool:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    return ok


def _canary() -> int:
    from tools.chroma_session_indexer import IndexedMessage, sync_message_to_chroma

    msg = IndexedMessage(
        message_id=1, session_id=SID, role="user",
        content="RL-094 D11 抽样读回金丝雀", source="canary", timestamp=time.time(),
    )
    return 0 if sync_message_to_chroma(msg) else 2


def d11() -> int:
    from tools.chroma_session_indexer import (
        _get_incremental_collection,
        delete_session_chroma_documents,
        message_doc_id,
    )

    fails = 0
    before = _counts()
    fails += 0 if _say("写入前基线可读", before > 0, f"embeddings={before}") else 1
    if _canary() != 0:
        return 2
    # B12：金丝雀落库之后，任何一条异常路径都必须把删除跑完——否则生产集合里
    # 留下一行 session_id=rl094-canary 的残行，漂移永久 +1，且下一次 d14 的
    # 「回基线」断言也会跟着错。删除放 finally，断言放 finally 之后。
    try:
        after = _counts()
        fails += 0 if _say("写入后 +1", after == before + 1, f"{before}→{after}") else 1

        doc_id = message_doc_id(SID, 1)
        col = _get_incremental_collection()
        got = col.get(ids=[doc_id], include=["documents", "metadatas"])
        ok = bool(got.get("ids")) and got["ids"][0] == doc_id
        fails += 0 if _say("按 doc id 读回命中", ok, doc_id) else 1
        doc = (got.get("documents") or [""])[0]
        fails += 0 if _say("正文逐字一致", doc == "RL-094 D11 抽样读回金丝雀", doc[:40]) else 1
        meta = (got.get("metadatas") or [{}])[0] or {}
        fails += 0 if _say("metadata session_id 一致", meta.get("session_id") == SID, str(meta.get("session_id"))) else 1
    finally:
        delete_session_chroma_documents(SID)

    back = _counts()
    fails += 0 if _say("删除后回基线", back == before, f"{after}→{back}") else 1
    print(json.dumps({"d11": "PASS" if not fails else "FAIL", "before": before, "after": after, "back": back}))
    return 0 if not fails else 2


def d14() -> int:
    from tools.chroma_session_indexer import _get_incremental_collection, delete_session_chroma_documents

    fails = 0
    base = _counts()
    if _canary() != 0:
        return 2
    drifted = _counts()
    fails += 0 if _say("违约：漂移 +1", drifted == base + 1, f"drift={drifted - base}") else 1
    delete_session_chroma_documents(SID)
    healed = _counts()
    fails += 0 if _say("收敛：漂移回 0", healed == base, f"drift={healed - base}") else 1
    ok_row = False
    try:
        from mimir_constants import get_mimir_home

        hist = Path(get_mimir_home()) / "data" / "p0_index_health_history.jsonl"
        if hist.exists():
            last = json.loads(hist.read_text(encoding="utf-8").strip().splitlines()[-1])
            ok_row = abs(int(last.get("drift_abs", 0))) <= 0
    except Exception:
        ok_row = False
    fails += 0 if _say("健康面末行 drift=0", ok_row) else 1
    print(json.dumps({"d14": "PASS" if not fails else "FAIL", "base": base, "healed": healed}))
    return 0 if not fails else 2


def d3() -> int:
    home = os.environ.get("MIMIR_AETHER_HOME", "")
    if not home:
        print("FAIL d3 需要隔离 MIMIR_AETHER_HOME（不许打生产主目录）")
        return 2
    code = (
        "import sys,time;sys.path.insert(0,%r);"
        "from tools.chroma_session_indexer import chroma_write_lock;"
        "import os;os.environ['MIMIR_CHROMA_LOCK_ROLE']='holder';"
        "\nwith chroma_write_lock(): time.sleep(3)"
    ) % str(REPO)
    holder = subprocess.Popen([sys.executable, "-c", code], env=dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    os.environ["MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S"] = "0.2"
    os.environ["MIMIR_CHROMA_LOCK_ROLE"] = "d3-probe"
    rc, msg = 0, ""
    try:
        from tools.chroma_session_indexer import ChromaWriteLockTimeout, chroma_write_lock, note_index_failure
        try:
            with chroma_write_lock():
                rc, msg = 2, "unexpected_acquire"
        except ChromaWriteLockTimeout as exc:
            rc, msg = 0, str(exc)
            note_index_failure("lock_timeout", exc, sink="rl094-d3")
    except Exception as exc:  # noqa: BLE001
        rc, msg = 2, f"{type(exc).__name__}: {exc}"
    holder.wait(timeout=10)

    fails = 0
    fails += 0 if _say("超时被抛出", rc == 0, msg[:60]) else 1
    data = Path(home) / "data"
    events = [json.loads(l) for l in (data / "chroma_write_events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    to_ev = [e for e in events if e.get("phase") == "acquire_failed" and e.get("result") == "timeout"]
    fails += 0 if _say("源1 账本 timeouts=1", len(to_ev) == 1, f"n={len(to_ev)}") else 1
    cnt = json.loads((data / "index_failure_counts.json").read_text(encoding="utf-8"))
    got = (cnt.get("lock_timeout") or {}).get("count", cnt.get("lock_timeout"))
    fails += 0 if _say("源2 失败计数=1", got == 1, f"lock_timeout={got}") else 1
    unpaired = len([e for e in events if e.get("phase") == "begin"]) - len([e for e in events if e.get("phase") == "end"])
    fails += 0 if _say("超时不污染 unpaired", unpaired == 0, f"unpaired={unpaired}") else 1
    print(json.dumps({"d3": "PASS" if not fails else "FAIL", "ledger_timeouts": len(to_ev), "failure_count": got}))
    return 0 if not fails else 2


if __name__ == "__main__":
    mode = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    fn = {"d11": d11, "d14": d14, "d3": d3}.get(mode)
    if not fn:
        print(__doc__)
        sys.exit(2)
    sys.exit(fn())
