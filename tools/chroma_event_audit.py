#!/usr/bin/env python3
"""D2/D13 —— chroma 写入事件账本审计（RL-20261020-094）。

判什么
------
账本 `~/.mimiraether/data/chroma_write_events.jsonl` 每行一条事件：
  begin / end / acquire_failed，带 pid、nonce、role、ts、hold_ms。
本脚本不信任任何自我陈述，只从事件序列算四个机器数：

  unpaired    : begin 没有配对的 end      —— 只该在进程被杀（SIGKILL）时 >0
  overlaps    : 不同 pid 的临界区区间相交 —— 必须恒为 0（锁的核心保证）
  timeouts    : acquire_failed/result=timeout 的条数
  errors      : acquire_failed/result=error + end/result=error

区间口径：begin.ts → end.ts（墙钟秒）。配对键 = (pid, nonce)，同键 FIFO。
样本纪律：n>=20 才出 p95，n<20 只报 max（不出分，避免拿 3 个样本吹分布）。

退出码：0 无违规；2 有违规（unpaired>0 或 overlaps>0）
用法：
  chroma_event_audit.py [--file PATH] [--json] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_events(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as fh:
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


def audit(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    open_map: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    timeouts = 0
    errors = 0

    for rec in records:
        phase = rec.get("phase")
        if phase == "begin":
            open_map.setdefault((rec.get("pid"), rec.get("nonce")), []).append(rec)
        elif phase == "end":
            key = (rec.get("pid"), rec.get("nonce"))
            queue = open_map.get(key) or []
            if queue:
                pairs.append((queue.pop(0), rec))
            if rec.get("result") == "error":
                errors += 1
        elif phase == "acquire_failed":
            if rec.get("result") == "timeout":
                timeouts += 1
            else:
                errors += 1

    unpaired = [b for q in open_map.values() for b in q]
    intervals = sorted((float(b["ts"]), float(e["ts"]), b.get("pid")) for b, e in pairs)

    overlaps = 0
    active: List[Tuple[float, Any]] = []
    for start, end, pid in intervals:
        active = [a for a in active if a[0] > start]
        overlaps += sum(1 for a in active if a[1] != pid)
        active.append((end, pid))

    holds = sorted(round((e - b) * 1000.0, 3) for b, e, _ in intervals)
    p95 = None
    if len(holds) >= 20:
        idx = max(0, min(len(holds) - 1, int(round(0.95 * (len(holds) - 1)))))
        p95 = holds[idx]

    return {
        "events": len(records),
        "begins": sum(1 for r in records if r.get("phase") == "begin"),
        "ends": sum(1 for r in records if r.get("phase") == "end"),
        "pairs": len(pairs),
        "unpaired": len(unpaired),
        "unpaired_detail": [
            {"pid": b.get("pid"), "nonce": b.get("nonce"), "ts": b.get("ts")} for b in unpaired[:5]
        ],
        "overlaps": overlaps,
        "timeouts": timeouts,
        "errors": errors,
        "samples": len(holds),
        "max_hold_ms": holds[-1] if holds else None,
        "p95_hold_ms": p95,
        "p95_note": "n>=20" if p95 is not None else f"n={len(holds)}<20·只报 max",
        "roles": sorted({str(r.get("role")) for r in records if r.get("role")}),
    }


def selftest() -> int:
    base = 1_000.0
    ok_seq = [
        {"phase": "begin", "ts": base, "pid": 1, "nonce": "a"},
        {"phase": "end", "ts": base + 0.1, "pid": 1, "nonce": "a"},
        {"phase": "begin", "ts": base + 0.2, "pid": 2, "nonce": "b"},
        {"phase": "end", "ts": base + 0.3, "pid": 2, "nonce": "b"},
    ]
    overlap = [
        {"phase": "begin", "ts": base, "pid": 1, "nonce": "a"},
        {"phase": "begin", "ts": base + 0.05, "pid": 2, "nonce": "b"},
        {"phase": "end", "ts": base + 0.2, "pid": 1, "nonce": "a"},
        {"phase": "end", "ts": base + 0.3, "pid": 2, "nonce": "b"},
    ]
    unpaired = [{"phase": "begin", "ts": base, "pid": 3, "nonce": "c"}]
    timeout = [{"phase": "acquire_failed", "ts": base, "pid": 4, "result": "timeout"}]

    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        print(("PASS " if cond else "FAIL ") + name)
        fails += 0 if cond else 1

    a = audit(ok_seq)
    check("顺序执行 overlaps=0", a["overlaps"] == 0 and a["pairs"] == 2 and a["unpaired"] == 0)
    b = audit(overlap)
    check("真重叠 overlaps=1", b["overlaps"] == 1)
    c = audit(unpaired)
    check("缺 end unpaired=1", c["unpaired"] == 1)
    d = audit(timeout)
    check("超时计 timeout=1 不污染 unpaired", d["timeouts"] == 1 and d["unpaired"] == 0)
    check("同键 FIFO 配对", audit(ok_seq + ok_seq[:2])["pairs"] == 3)
    return 2 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.file:
        path = Path(args.file)
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from mimir_constants import get_mimir_home

        path = Path(get_mimir_home()) / "data" / "chroma_write_events.jsonl"

    res = audit(load_events(path))
    res["file"] = str(path)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"file={res['file']}")
        print(f"  events={res['events']} begins={res['begins']} ends={res['ends']} pairs={res['pairs']}")
        print(f"  unpaired={res['unpaired']}  overlaps={res['overlaps']}  "
              f"timeouts={res['timeouts']}  errors={res['errors']}")
        print(f"  hold_ms: max={res['max_hold_ms']} p95={res['p95_hold_ms']} ({res['p95_note']})")
        print(f"  roles={res['roles']}")
    return 2 if (res["unpaired"] or res["overlaps"]) else 0


if __name__ == "__main__":
    sys.exit(main())
