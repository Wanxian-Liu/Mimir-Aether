#!/usr/bin/env python3
"""B9 一周度量采集器（RS6）。

背景：B9（阈值按「有效窗口」定 · commit 41fd67c）附条件「重启后一周采集四项度量」，到期未交 = 重开。
从**既有日志**机械抽取四项度量，输出可复核 JSON 快照——不新增打点、不改运行时。

四项度量（B9 卡 §5）：
  1. 每轮 prompt_tokens 分布        <- agent.log `[S2-cache] prompt=`
  2. 缓存命中率（token 加权）        <- agent.log `[S2-cache] hit= / prompt=`
  3. 压缩次数与 before->after 计数   <- agent.log `[COMPRESS-INIT] / [COMPRESS] result|skip|abort`
  4. turn-N 约束准确率              <- **无既有数据源** -> null + reason（诚实标注，不编）

用法： .venv/bin/python3 scripts/b9_weekly_metrics.py [--print]
"""
from __future__ import annotations
import argparse, datetime, json, pathlib, re, statistics

HOME = pathlib.Path.home() / ".mimiraether"
DEFAULT_LOG = HOME / "logs" / "agent.log"
DEFAULT_OUT = HOME / "data" / "ops" / "b9-weekly-metrics.json"

CACHE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[^\n]*\[S2-cache\] prompt=(?P<prompt>\d+) hit=(?P<hit>\d+)")
INIT_RE = re.compile(r"\[COMPRESS-INIT\][^\n]*threshold_tokens=(?P<thr>\d+)[^\n]*source=(?P<src>\S+)")
STATE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[^\n]*\[COMPRESS\] (?P<state>skip|abort|result)")
TOK_RE = re.compile(r"tokens=(\d+)")
MSGS_RE = re.compile(r"msgs=(\d+)(?:->(\d+))?")
REASON_RE = re.compile(r"reason=(\w+)")


def q(vals, quant):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round(quant * (len(s) - 1)))))]


def collect(log_path):
    txt = log_path.read_text(encoding="utf-8", errors="ignore")
    today = datetime.date.today().isoformat()
    calls, comp, inits = [], [], []
    for line in txt.splitlines():
        m = CACHE_RE.match(line)
        if m and m.group("ts").startswith(today):
            calls.append((int(m.group("prompt")), int(m.group("hit"))))
            continue
        m = INIT_RE.search(line)
        if m:
            inits.append({"threshold_tokens": int(m.group("thr")), "source": m.group("src")})
            continue
        m = STATE_RE.match(line)
        if m and m.group("ts").startswith(today):
            tk, mg, rs = TOK_RE.search(line), MSGS_RE.search(line), REASON_RE.search(line)
            comp.append({"state": m.group("state"),
                         "tokens": int(tk.group(1)) if tk else None,
                         "msgs": [int(mg.group(1)), int(mg.group(2) or mg.group(1))] if mg else None,
                         "reason": rs.group(1) if rs else None})
    prompts = [c[0] for c in calls]
    hit = sum(c[1] for c in calls)
    tot = sum(c[0] for c in calls)
    thr = inits[-1]["threshold_tokens"] if inits else None
    results = [c for c in comp if c["state"] == "result"]
    return {
        "date": today, "log": str(log_path),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "m1_prompt_tokens": {"samples": len(prompts), "min": min(prompts) if prompts else None,
            "p50": q(prompts, 0.50), "p90": q(prompts, 0.90), "max": max(prompts) if prompts else None,
            "mean": round(statistics.fmean(prompts), 1) if prompts else None},
        "m2_cache": {"weighted_hit_pct": round(100.0 * hit / tot, 2) if tot else None,
            "prompt_tokens_total": tot, "hit_tokens_total": hit},
        "m3_compress": {"threshold_tokens": thr,
            "threshold_source": inits[-1]["source"] if inits else None, "init_lines": len(inits),
            "skip": sum(1 for c in comp if c["state"] == "skip"),
            "abort": sum(1 for c in comp if c["state"] == "abort"),
            "abort_noop": sum(1 for c in comp if c["state"] == "abort" and c["reason"] == "noop"),
            "result": len(results), "real_compressions": len(results),
            "inner_tokens_last": comp[-1]["tokens"] if comp else None,
            "calls_at_or_above_threshold": sum(1 for p in prompts if thr and p >= thr)},
        "m4_turnN_constraint_accuracy": {"value": None,
            "reason": "无既有数据源：turn-N 约束抽取准确率未在任何日志/遥测中；需先定口径并补打点（RS5 之后的独立项）"},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(DEFAULT_LOG))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--print", dest="show", action="store_true")
    a = ap.parse_args()
    snap = collect(pathlib.Path(a.log))
    outp = pathlib.Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    data = {"runs": []}
    if outp.exists():
        try:
            data = json.loads(outp.read_text(encoding="utf-8"))
        except Exception:
            data = {"runs": []}
    data.setdefault("runs", [])
    data["runs"] = [r for r in data["runs"] if r.get("date") != snap["date"]] + [snap]
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(snap, ensure_ascii=False, indent=1) if a.show else f"snapshot {snap['date']} -> {outp} (runs={len(data['runs'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
