#!/usr/bin/env python3
"""RS11 前置探针分析器（四方裁决 §29 Q17 · 2026-09-14）。

`[RUN] phase=finish` 行现在带 ``in_sha1`` / ``resp_sha1``。本脚本把它们配对：

  * 同一 ``resp_sha1`` 出现在 **>1 个 trace_id** 且 ``in_sha1`` 不同
    ⇒ 同一份回复被投递了两次（RS11 现象 = 08-18 起 ≥8 组的形态）
  * 同一 ``resp_sha1`` 且 **同一 trace_id** ⇒ 同一次 run 内重复（另一族）

用法::

    python3 scripts/analyze_run_sha1_dupes.py                       # 默认 gateway.log
    python3 scripts/analyze_run_sha1_dupes.py --log PATH --days 7

只读；无副作用。数据要先积累（探针本轮才上线）：样本 0 时输出
``no_samples`` —— **不是 PASS**，别读成"无重复"（RS17：无数据 ≠ 阴性）。
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

DEFAULT_LOG = Path.home() / ".mimiraether" / "logs" / "gateway.log"

_FIELD = re.compile(r"(\w+)=(\S*)")


def parse_finish_lines(text: str):
    """yield dict(字段) 给每条 [RUN] phase=finish 行。"""
    for line in text.splitlines():
        if "[RUN]" not in line or "phase=finish" not in line:
            continue
        fields = dict(_FIELD.findall(line))
        if fields.get("resp_sha1"):
            yield fields


def analyze(records) -> dict:
    by_resp = defaultdict(list)
    for rec in records:
        by_resp[rec.get("resp_sha1", "-")].append(rec)
    cross_run, same_run = [], []
    for resp_sha1, recs in by_resp.items():
        if len(recs) < 2:
            continue
        traces = {r.get("trace_id", "") for r in recs}
        ins = {r.get("in_sha1", "-") for r in recs}
        entry = {
            "resp_sha1": resp_sha1,
            "count": len(recs),
            "traces": sorted(traces),
            "in_sha1": sorted(ins),
            "resp_len": recs[0].get("resp_len"),
        }
        if len(traces) > 1 and len(ins) > 1:
            cross_run.append(entry)
        elif len(traces) == 1:
            same_run.append(entry)
    total = len(by_resp)
    dup_traces = sum(e["count"] for e in cross_run)
    return {
        "samples": sum(len(v) for v in by_resp.values()),
        "distinct_resp": total,
        "cross_run_dupes": cross_run,
        "same_run_repeats": same_run,
        "extra_deliveries": dup_traces - len(cross_run),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument(
        "--rotate",
        type=int,
        default=0,
        help="同时扫 gateway.log.1..N（轮转文件）",
    )
    args = parser.parse_args()

    files = [args.log] + [Path(f"{args.log}.{i}") for i in range(1, args.rotate + 1)]
    text = ""
    for path in files:
        if path.exists():
            text += path.read_text(encoding="utf-8", errors="replace")
            text += "\n"
    result = analyze(parse_finish_lines(text))

    print(f"log={args.log}")
    print(f"samples={result['samples']} distinct_resp={result['distinct_resp']}")
    if not result["samples"]:
        print("VERDICT: no_samples —— 探针尚无数据（探针本轮才上线）；")
        print("         无数据 ≠ 阴性，别读成'无重复'（RS17）")
        return 2
    print(f"cross_run_dupes={len(result['cross_run_dupes'])} "
          f"extra_deliveries={result['extra_deliveries']} "
          f"same_run_repeats={len(result['same_run_repeats'])}")
    for entry in result["cross_run_dupes"][:20]:
        print(f"  DUP resp_sha1={entry['resp_sha1']} count={entry['count']} "
              f"resp_len={entry['resp_len']} traces={entry['traces']} in_sha1={entry['in_sha1']}")
    print("VERDICT: " + ("DUPES_FOUND" if result["cross_run_dupes"] else "clean"))
    return 1 if result["cross_run_dupes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
