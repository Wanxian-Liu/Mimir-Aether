#!/usr/bin/env python3
"""Resumable, crash-isolated, idempotent backfill of sessions_search.db -> Chroma.

Reuses existing primitives from tools/chroma_session_indexer.py (no new
embedding/upsert code):
  message_doc_id() -> idempotent doc id f"{session_id}:{message_id}"
  is_garbage_content() -> same P0 garbage filter as the live indexer
  _upsert_batch() -> upsert(ids=, documents=, metadatas=)
  get_chroma_collection()/resolve_embedding_function() -> same backend (bge-m3)

Adds only what the bulk path lacked: per-session checkpoint (last_session /
last_rowid), crash isolation (one bad session is recorded, run continues),
and explicit per-session readings.

Usage:
  python3 scripts/chroma_backfill_full.py --only-session <sid> --rebuild
  python3 scripts/chroma_backfill_full.py --batch-sessions 20
  python3 scripts/chroma_backfill_full.py --verify-only --verify-all-sessions
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mimir_constants import get_mimir_home  # noqa: E402

DATA = Path(get_mimir_home()) / "data"
# Overridable so an isolated canary run cannot clobber the checkpoint of an
# in-flight full run (2026-10-19: a smoke run overwrote ckpt once).
CKPT = Path(os.environ.get("MIMIR_BACKFILL_CKPT", str(DATA / "chroma_backfill_ckpt.json")))
REPORT = Path(os.environ.get("MIMIR_BACKFILL_REPORT", str(DATA / "chroma_backfill_report.json")))
FAULT = Path(os.environ.get("MIMIR_BACKFILL_FAULT", str(DATA / "chroma_backfill_fault.log")))

from tools.chroma_session_indexer import (  # noqa: E402
    IndexedMessage,
    _upsert_batch,
    chroma_write_lock,
    get_chroma_collection,
    is_garbage_content,
    message_doc_id,
    resolve_embedding_function,
)

BATCH_ROWS = 128


def rss_hwm_mb() -> int:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    return -1


def save_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def fault(msg: str) -> None:
    """Append a forensic line to FAULT (flushed+fsync) and mirror to stdout.

    point5: failures must land in fault.log, never be skipped silently.
    """
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}\n"
    try:
        with FAULT.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:  # never let logging kill the run
        print(f"[FAULT-LOG-ERROR] {type(exc).__name__}: {exc}", flush=True)
    print(f"[FAULT] {msg}", flush=True)


def load_ckpt() -> Dict[str, Any]:
    if CKPT.is_file():
        try:
            return json.loads(CKPT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "last_session": "", "last_rowid": 0,
            "done_sessions": [], "failures": []}


def source_sessions(db: Path) -> List[str]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT session_id, MIN(id) AS first_id FROM messages "
            "WHERE content IS NOT NULL AND TRIM(content) != '' "
            "GROUP BY session_id ORDER BY first_id, session_id"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def session_rows(db: Path, session_id: str) -> List[IndexedMessage]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT m.id, m.role, m.content, m.tool_name, m.timestamp, "
            "COALESCE(s.source,'unknown') FROM messages m "
            "LEFT JOIN sessions s ON m.session_id = s.session_id "
            "WHERE m.session_id = ? AND m.content IS NOT NULL AND TRIM(m.content) != '' "
            "ORDER BY m.id", (session_id,),
        ).fetchall()
    finally:
        conn.close()
    out: List[IndexedMessage] = []
    for mid, role, content, tool_name, ts, source in rows:
        if is_garbage_content(content):
            continue
        out.append(IndexedMessage(
            message_id=int(mid), session_id=session_id, role=str(role or "unknown"),
            content=str(content), source=str(source or "unknown"),
            timestamp=float(ts or 0.0), tool_name=str(tool_name) if tool_name else None,
        ))
    return out


def chroma_ids_for(col: Any, session_id: str) -> set:
    have: set = set()
    offset = 0
    while True:
        got = col.get(where={"session_id": session_id}, include=[],
                      limit=1000, offset=offset).get("ids") or []
        if not got:
            break
        have |= set(got)
        offset += len(got)
        if len(got) < 1000:
            break
    return have


def verify(col: Any, db: Path, sessions: List[str], verify_all: bool) -> int:
    total_want = total_have = 0
    bad = []
    for sid in sessions:
        want = {message_doc_id(m.session_id, m.message_id) for m in session_rows(db, sid)}
        have = chroma_ids_for(col, sid) if verify_all else set()
        total_want += len(want)
        if verify_all:
            total_have += len(have)
            if have != want:
                bad.append({"session_id": sid, "want": len(want), "have": len(have),
                            "missing": len(want - have), "orphans": len(have - want)})
    print(json.dumps({
        "chroma_total": col.count(),
        "source_indexable_total": total_want,
        "sessions": len(sessions),
        "per_session_have": total_have if verify_all else None,
        "mismatched_sessions": len(bad),
        "first_mismatches": bad[:10],
    }, ensure_ascii=False, indent=2), flush=True)
    return 0 if not bad or not verify_all else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DATA / "sessions_search.db"))
    ap.add_argument("--chroma-dir", default=str(DATA / "chroma_sessions"))
    ap.add_argument("--batch-sessions", type=int, default=20)
    ap.add_argument("--only-session", default="")
    ap.add_argument("--limit-sessions", type=int, default=0)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--verify-all-sessions", action="store_true")
    ap.add_argument("--embed-model",
                    default=os.environ.get("MIMIR_EMBED_MODEL",
                                          str(Path.home() / "models" / "bge-m3")))
    args = ap.parse_args()

    faulthandler.enable(open(FAULT, "a"))
    db = Path(args.db)
    if not db.is_file():
        print(f"FATAL db missing: {db}", flush=True)
        return 2

    t_start = time.time()
    ckpt = ({"version": 1, "last_session": "", "last_rowid": 0,
             "done_sessions": [], "failures": []} if args.fresh else load_ckpt())
    sessions = source_sessions(db)
    if args.only_session:
        sessions = [s for s in sessions if s == args.only_session]
        if not sessions:
            print(f"FATAL session not in db: {args.only_session}", flush=True)
            return 2
    if args.limit_sessions:
        sessions = sessions[: args.limit_sessions]

    ef = resolve_embedding_function(model=args.embed_model or None)
    col = get_chroma_collection(Path(args.chroma_dir), embedding_function=ef)
    print(f"PLAN sessions={len(sessions)} chroma_before={col.count()} embed={ef.name()} "
          f"batch_sessions={args.batch_sessions} rebuild={args.rebuild} "
          f"verify_only={args.verify_only}", flush=True)

    if args.verify_only:
        return verify(col, db, sessions, args.verify_all_sessions)

    done = list(ckpt.get("done_sessions") or [])
    failures: List[Dict[str, Any]] = list(ckpt.get("failures") or [])
    failures_before = len(failures)
    built = 0
    batch_index = 0
    batch_start = time.time()
    per_session: Dict[str, Dict[str, Any]] = {}

    for idx, sid in enumerate(sessions, 1):
        if not args.only_session and not args.rebuild and sid in done:
            continue
        t0 = time.time()
        try:
            rows = session_rows(db, sid)
            if args.rebuild:
                with chroma_write_lock():
                    col.delete(where={"session_id": sid})
            start_rowid = 0
            if (not args.rebuild and ckpt.get("last_session") == sid
                    and int(ckpt.get("last_rowid") or 0) > 0):
                start_rowid = int(ckpt["last_rowid"])
            pending = [m for m in rows if m.message_id > start_rowid]
            buf: List[IndexedMessage] = []
            upserted = 0
            for msg in pending:
                buf.append(msg)
                if len(buf) >= BATCH_ROWS:
                    upserted += _upsert_batch(col, buf)
                    ckpt.update({"last_session": sid, "last_rowid": buf[-1].message_id,
                                 "done_sessions": done, "failures": failures,
                                 "updated_at": time.time()})
                    save_json_atomic(CKPT, ckpt)
                    buf = []
            if buf:
                upserted += _upsert_batch(col, buf)
            have_ids = chroma_ids_for(col, sid)
            want_ids = {message_doc_id(m.session_id, m.message_id) for m in rows}
            missing = len(want_ids - have_ids)
            orphans = have_ids - want_ids
            if orphans:
                with chroma_write_lock():
                    col.delete(ids=sorted(orphans))
                have_ids -= orphans
            status = "OK" if missing == 0 and have_ids == want_ids else "MISMATCH"
            per_session[sid] = {"want": len(want_ids), "have": len(have_ids),
                                "upserted": upserted, "missing": missing,
                                "orphans_deleted": len(orphans), "status": status,
                                "secs": round(time.time() - t0, 2)}
            if status != "OK":
                failures.append({"session_id": sid, "stage": "verify",
                                 "error": f"missing={missing} have={len(have_ids)}",
                                 "ts": time.time()})
                fault(f"verify {sid} missing={missing} have={len(have_ids)} "
                      f"want={len(want_ids)} upserted={upserted}")
            if sid not in done:
                done.append(sid)
            built += 1
            ckpt.update({"last_session": sid, "last_rowid": 0, "done_sessions": done,
                         "failures": failures, "updated_at": time.time()})
            save_json_atomic(CKPT, ckpt)
        except Exception as exc:  # crash isolation
            failures.append({"session_id": sid, "stage": "index",
                             "error": f"{type(exc).__name__}: {exc}", "ts": time.time()})
            ckpt.update({"failures": failures, "last_session": sid, "last_rowid": 0,
                         "done_sessions": done, "updated_at": time.time()})
            save_json_atomic(CKPT, ckpt)
            fault(f"index {sid} {type(exc).__name__}: {exc}")

        if idx % args.batch_sessions == 0 or idx == len(sessions):
            batch_index += 1
            print(f"PROGRESS batch={batch_index} seen={idx}/{len(sessions)} built={built} "
                  f"done_total={len(done)} chroma={col.count()} "
                  f"batch_secs={round(time.time() - batch_start, 1)} "
                  f"total_secs={round(time.time() - t_start, 1)} rss_hwm_mb={rss_hwm_mb()} "
                  f"failures={len(failures)}", flush=True)
            batch_start = time.time()

    report = {
        "generated_at": time.time(),
        "sessions_in_run": len(sessions),
        "sessions_built_this_run": built,
        "done_total": len(done),
        "chroma_count": col.count(),
        "failures": failures,
        "per_session": per_session,
        "elapsed_secs": round(time.time() - t_start, 1),
        "rss_hwm_mb": rss_hwm_mb(),
        "embed": ef.name(),
        "embed_model": args.embed_model,
    }
    save_json_atomic(REPORT, report)
    print(f"DONE built={built} chroma={col.count()} failures={len(failures)} "
          f"elapsed={report['elapsed_secs']}s rss_hwm_mb={report['rss_hwm_mb']}", flush=True)
    new_failures = len(failures) - failures_before
    if new_failures:
        fault(f"RUN end with {new_failures} new failure(s); see report {REPORT}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
