#!/usr/bin/env python3
"""f2c_sample_ledger.py — F2-c 补样台账（2026-09-16 · 终裁③ 折中判据的工程件）

终裁 ③：**不做全量**；先把 `n=4` 补到 `n >= 20` 再判（Loki 统计质疑成立 + 我的降级方向成立）。
口径（终裁时钉死，防事后漂移）：
  - 样本单位 = **唯一事件**（同 `session_id` 的重试快照去重；上轮 4 段里 3 段同 sid ⇒ 唯一事件数 1）
  - 判据 = 唯一事件中「执行器被长活儿占满」的比例 + **Wilson 区间**
  - 补样靠真实事件积累（非单方制造）⇒ 待观测项，**未声称达标**

本脚本（只读日志 + 可选追加台账）：
  1. 解析 `[INDEX] hygiene-compress begin|end|TIMEOUT sid=.. docs=.. [elapsed=..s]`
     （gateway.log 二进制安全读取）
  2. 配对 begin → 同 sid 的 end/TIMEOUT（FIFO）⇒ 一次**作业跑**；未配对 = orphan，**不进分母**
  3. 两种单位都算并报出：runs（会高估）· incidents（唯一事件 = 同 sid 间隔 <= gap 归并；**判据所用 n**）
  4. **Wilson 95% 区间**
  5. 决策规则（先于数据钉死）：n < min_n ⇒ INSUFFICIENT（样本不足·不下结论）
     否则 下界>thresh ⇒ IMPLEMENT · 上界<thresh ⇒ DOWNGRADE · 否则 KEEP_OBSERVING

用法：python3 f2c_sample_ledger.py [--json] [--append] [--merge-gap 30]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

DEFAULT_MIN_N = 20
DEFAULT_THRESH = 0.05
DEFAULT_MERGE_GAP_MIN = 45.0
Z = 1.959963984540054

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?(?P<ms>\d{3})?\s+\w+\s+"
    r"gateway\.session:\s+\[INDEX\]\s+hygiene-compress\s+"
    r"(?P<kind>begin|end|TIMEOUT)\s+sid=(?P<sid>\S+)\s+docs=(?P<docs>\d+)"
    r"(?:.*?elapsed=(?P<elapsed>[\d.]+)s)?"
)


def parse_ts(ts: str):
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def read_events(log_paths):
    """解析全部事件行。二进制安全（gateway.log 含二进制字节）。"""
    events, notes = [], []
    for p in log_paths:
        p = Path(p)
        if not p.exists():
            notes.append(f"skip(missing): {p}")
            continue
        raw = p.open("rb").read()
        for line in raw.decode("utf-8", errors="replace").splitlines():
            m = _LINE_RE.search(line)
            if not m:
                continue
            try:
                ts = parse_ts(m.group("ts"))
            except ValueError:
                # 不静默丢：形状对但时间戳非法（实测坑：夹具 `{mm}` 未补零 → "10:0:00"）
                notes.append(f"bad_ts(skipped): {line[:70]}")
                continue
            events.append({
                "ts": m.group("ts"), "dt": ts, "kind": m.group("kind"),
                "sid": m.group("sid"), "docs": int(m.group("docs")),
                "elapsed": float(m.group("elapsed")) if m.group("elapsed") else None,
                "source": str(p),
            })
    # 去重：errors.log 会**镜像** gateway.log 的部分行（实测 3 条 TIMEOUT 两处都有）
    # ⇒ 不去重会把同一事件当成「1 条配对 + 1 条孤儿」，n 虚高、比例失真。
    dedup, seen = [], set()
    for e in events:
        key = (e["ts"], e["sid"], e["kind"], e["docs"])
        if key in seen:
            notes.append(f"dedup: {key}")
            continue
        seen.add(key)
        dedup.append(e)
    dedup.sort(key=lambda e: e["dt"])
    return dedup, notes


def pair_runs(events):
    """begin ↔ (end|TIMEOUT) 按同 sid FIFO 配对。返回 (runs, orphans)。"""
    open_by_sid = {}
    runs, orphans = [], []
    for e in events:
        if e["kind"] == "begin":
            open_by_sid.setdefault(e["sid"], []).append(e)
            continue
        queue = open_by_sid.get(e["sid"]) or []
        if not queue:
            runs.append({"sid": e["sid"], "begin": None, "end": e,
                         "start": None, "finish": e["dt"], "outcome": "orphan_end"})
            continue
        b = queue.pop(0)
        runs.append({"sid": e["sid"], "begin": b, "end": e, "start": b["dt"], "finish": e["dt"],
                     "outcome": "timeout" if e["kind"] == "TIMEOUT" else "ok",
                     "docs": e["docs"], "elapsed": e["elapsed"]})
    for sid, queue in open_by_sid.items():
        for b in queue:
            orphans.append({"sid": sid, "begin": b, "outcome": "orphan_begin"})
    return runs, orphans


def merge_incidents(runs, gap_min):
    """唯一事件 = 同 sid 内相邻事件间隔 <= gap_min 归并为一件事。

    只吃**已配对**的作业跑（begin+结论）；未配对者（orphan_*）不完整 ⇒ 不进比例。
    """
    out = []
    by_sid = {}
    for r in [x for x in runs if x.get("start") is not None]:
        by_sid.setdefault(r["sid"], []).append(r)
    for sid, rs in by_sid.items():
        rs = sorted(rs, key=lambda r: r.get("start") or datetime.max)
        cur = None
        for r in rs:
            if cur is None:
                cur = {"sid": sid, "runs": [r], "timeouts": 1 if r["outcome"] == "timeout" else 0,
                       "first": r.get("start"), "last": r.get("finish")}
                continue
            gap = None
            if r.get("start") and cur["last"]:
                gap = (r["start"] - cur["last"]).total_seconds() / 60.0
            if gap is not None and gap <= gap_min:
                cur["runs"].append(r)
                cur["timeouts"] += 1 if r["outcome"] == "timeout" else 0
                cur["last"] = r.get("finish")
            else:
                out.append(cur)
                cur = {"sid": sid, "runs": [r], "timeouts": 1 if r["outcome"] == "timeout" else 0,
                       "first": r.get("start"), "last": r.get("finish")}
        if cur is not None:
            out.append(cur)
    return sorted(out, key=lambda i: i["first"] or datetime.max)


def wilson(k, n, z=Z):
    """Wilson score interval（小样本仍保形）。"""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def decide(n, lo, hi, min_n, thresh):
    """决策规则（先于数据钉死）。"""
    if n < min_n:
        return {"verdict": "INSUFFICIENT",
                "why": f"n={n} < min_n={min_n} ⇒ 按终裁③ 样本不足·不下结论"
                       f"（Wilson [{lo:.3f},{hi:.3f}] 过宽，支持不了任一方向）"}
    if lo > thresh:
        return {"verdict": "IMPLEMENT",
                "why": f"Wilson 下界 {lo:.3f} > thresh {thresh} ⇒ 长活儿占满非罕见 ⇒ F2-c 值得实施"}
    if hi < thresh:
        return {"verdict": "DOWNGRADE",
                "why": f"Wilson 上界 {hi:.3f} < thresh {thresh} ⇒ 罕见 ⇒ 降级为可选兜底"}
    return {"verdict": "KEEP_OBSERVING",
            "why": f"Wilson [{lo:.3f},{hi:.3f}] 跨越 thresh {thresh} ⇒ 继续观测"}


def _mimir_home_candidates():
    """候选 home（**不再用 `Path.home()/'.mimiraether'` 单点猜**）。"""
    out = []
    for k in ("MIMIR_HOME", "MIMIR_AETHER_HOME"):
        v = os.environ.get(k)
        if v and v.strip():
            out.append(Path(v.strip()))
    out.append(Path.home())
    out.append(Path.home() / ".mimiraether")
    return out


def default_paths(home=None):
    """解析日志目录。

    2026-09-16 实测坑（第 3 次同族）：本机 HOME 就是 mimir home ⇒ `Path.home()/'.mimiraether'`
    得到嵌套假路径 `…/.mimiraether/.mimiraether/logs`（**该目录因早先事故真的存在**）
    ⇒ 旧写法「logs 目录存在即用」被骗过 ⇒ 扫到 0 事件，判据静默失真（`events=0` 看着像「没事件」）。
    修法：候选按序，**优先挑真的含 gateway.log/errors.log 的那一个**，而不是「目录存在」。
    """
    cands = [Path(home)] if home else _mimir_home_candidates()
    logdirs = [c / "logs" for c in cands]
    for lg in logdirs:
        if (lg / "gateway.log").exists() or (lg / "errors.log").exists():
            return [lg / "gateway.log", lg / "errors.log", lg / "errors.log.1", lg / "gateway.log.1"]
    for lg in logdirs:
        if lg.is_dir():
            return [lg / "gateway.log", lg / "errors.log", lg / "errors.log.1", lg / "gateway.log.1"]
    return [logdirs[0] / "gateway.log", logdirs[0] / "errors.log"]


def build(log_paths, min_n=DEFAULT_MIN_N, thresh=DEFAULT_THRESH, gap_min=DEFAULT_MERGE_GAP_MIN):
    events, notes = read_events(log_paths)
    runs, orphans = pair_runs(events)
    incidents = merge_incidents(runs, gap_min)
    paired = [r for r in runs if r.get("start") is not None]
    unpaired = [r for r in runs if r.get("start") is None]
    n_runs = len(paired)
    k_runs = sum(1 for r in paired if r["outcome"] == "timeout")
    n_inc = len(incidents)
    k_inc = sum(1 for i in incidents if i["timeouts"] > 0)
    lo_r, hi_r = wilson(k_runs, n_runs)
    lo_i, hi_i = wilson(k_inc, n_inc)
    verdict = decide(n_inc, lo_i, hi_i, min_n, thresh)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "unit_definitions": {
            "runs": "每次作业跑=1 样本（同事故多次重试各算一次 ⇒ 高估）",
            "incidents": f"唯一事件=同 sid 相邻间隔 <= {gap_min}min 归并（终裁口径·判据所用 n）",
        },
        "counts": {"events": len(events), "runs": n_runs, "timeout_runs": k_runs,
                   "orphans": len(orphans), "unpaired_ends": len(unpaired),
                   "incidents": n_inc, "timeout_incidents": k_inc},
        "wilson": {"runs": [round(lo_r, 4), round(hi_r, 4)],
                   "incidents": [round(lo_i, 4), round(hi_i, 4)]},
        "rate": {"runs": round(k_runs / n_runs, 4) if n_runs else None,
                 "incidents": round(k_inc / n_inc, 4) if n_inc else None},
        "rule": {"min_n": min_n, "thresh": thresh, "merge_gap_min": gap_min},
        "verdict": verdict["verdict"], "why": verdict["why"],
        "detail": {"runs": [{"sid": r["sid"], "outcome": r["outcome"],
                             "start": r["start"].strftime("%Y-%m-%d %H:%M:%S") if r.get("start") else None,
                             "docs": r.get("docs"), "elapsed": r.get("elapsed")} for r in paired],
                   "incidents": [{"sid": i["sid"], "runs": len(i["runs"]), "timeouts": i["timeouts"],
                                  "first": i["first"].strftime("%Y-%m-%d %H:%M:%S") if i["first"] else None,
                                  "last": i["last"].strftime("%Y-%m-%d %H:%M:%S") if i["last"] else None}
                                 for i in incidents]},
        "notes": notes,
    }


def append_ledger(rec, home=None):
    """幂等追加（按 ts+sid+outcome）。返回 (path, added)。路径解析与 default_paths 同源。"""
    lg = default_paths(home)[0].parent
    lp = lg.parent / "data" / "ops" / "f2c_events.jsonl"
    lp.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if lp.exists():
        for line in lp.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                if d.get("kind") == "run":
                    seen.add((d.get("ts"), d.get("sid"), d.get("outcome")))
            except json.JSONDecodeError:
                continue
    added = 0
    with lp.open("a", encoding="utf-8") as fh:
        for r in rec["detail"]["runs"]:
            key = (r["start"], r["sid"], r["outcome"])
            if key in seen:
                continue
            fh.write(json.dumps({"kind": "run", "ts": r["start"], "sid": r["sid"],
                                 "outcome": r["outcome"], "docs": r["docs"],
                                 "elapsed": r["elapsed"], "source": "f2c_sample_ledger"},
                                ensure_ascii=False) + "\n")
            added += 1
    return lp, added


def main(argv=None):
    ap = argparse.ArgumentParser(description="F2-c 补样台账（终裁③ 口径）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--merge-gap", type=float, default=DEFAULT_MERGE_GAP_MIN)
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    ap.add_argument("--thresh", type=float, default=DEFAULT_THRESH)
    args = ap.parse_args(argv)
    rec = build(default_paths(), min_n=args.min_n, thresh=args.thresh, gap_min=args.merge_gap)
    if args.append:
        lp, added = append_ledger(rec)
        rec["ledger"] = {"path": str(lp), "added": added}
    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0
    c = rec["counts"]
    print(f"events={c['events']} runs={c['runs']}(timeout {c['timeout_runs']}) "
          f"orphans={c['orphans']} unpaired_ends={c.get('unpaired_ends')} "
          f"incidents={c['incidents']}(timeout {c['timeout_incidents']})")
    print(f"rate  runs={rec['rate']['runs']} {rec['wilson']['runs']}  |  "
          f"incidents={rec['rate']['incidents']} {rec['wilson']['incidents']}")
    print(f"VERDICT: {rec['verdict']} -- {rec['why']}")
    for i in rec["detail"]["incidents"]:
        print(f"  incident {i['sid']} runs={i['runs']} timeouts={i['timeouts']} {i['first']} -> {i['last']}")
    if rec.get("ledger"):
        print(f"ledger: {rec['ledger']['path']} (+{rec['ledger']['added']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
