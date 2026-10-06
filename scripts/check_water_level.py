#!/usr/bin/env python3
"""F3 · 自身水位阈值出声（第 9 单 · A 档 #4 · 2026-10-07）。

病灶（审计卡 §7③「部分驳」· 盘上实证）：水位计**已在**，缺「到线出声」——
  会话：agent/prompt_builder.py 注入 [context-usage] … 只**显示**，无台账行、无 rc。
  记忆：scripts/check_memory_hygiene.py 有 rc，但**无消费者**（grep 仅命中自身+单测）。
⇒ 真缺口 = 阈值命中 ⇒ 台账新行 + rc 非 0；**不是再建一套水位**。

复用（不新造第二套水位）：
  1 记忆读数 tools.memory_tool（get_memory_store/_char_count/_char_limit/MAX_ENTRY_CHARS）
  2 会话读数 agent.context_usage_snapshot.read_context_usage_snapshot()
  3 阈值口径 scripts.check_memory_hygiene.USAGE_LIMIT_PCT（导入，不可得才回落 85.0）

rc 语义（错误语义不可裁剪）：0 OK / 2 OVER / 3 UNREADABLE / 4 LEDGER_FAIL
  优先级 UNREADABLE(3) > LEDGER_FAIL(4) > OVER(2) > OK(0)；未越阈也打印 OK 行（禁空白静默）。
台账：<home>/data/ops/water_level_events.jsonl，append-only，**仅越阈**追加一行。
用法：python3 scripts/check_water_level.py [--json|--selftest|--no-ledger|--home DIR]
回滚：纯只读 + 一个 append-only 台账；删本文件即回滚。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RC_OK, RC_OVER, RC_UNREADABLE, RC_LEDGER_FAIL = 0, 2, 3, 4
TRUNC_MARK = "[" + "..." + "] (truncated)"
LEDGER_NAME = "water_level_events.jsonl"


def memory_limit_pct() -> float:
    """复用 scripts/check_memory_hygiene.py 的阈值口径（不另立标准）。"""
    try:
        here = str(Path(__file__).resolve().parent)
        if here not in sys.path:
            sys.path.insert(0, here)
        from check_memory_hygiene import USAGE_LIMIT_PCT  # type: ignore

        return float(USAGE_LIMIT_PCT)
    except Exception:
        return 85.0


def evaluate_memory_row(target: str, chars: int, limit: int, entries: List[str],
                        max_entry_chars: int = 1200) -> Dict[str, Any]:
    """pure 判定（读路径与 selftest 共用，防两处口径漂移）。"""
    pct = (chars / limit * 100) if limit else 0.0
    mx = max((len(e) for e in entries), default=0)
    trunc = sum(1 for e in entries if TRUNC_MARK in e)
    lim_pct = memory_limit_pct()
    reasons: List[str] = []
    if mx > max_entry_chars:
        reasons.append("max_entry %d > %d" % (mx, max_entry_chars))
    if pct > lim_pct:
        reasons.append("usage %.1f%% > %.1f%%" % (pct, lim_pct))
    if trunc:
        reasons.append("trunc_markers %d" % trunc)
    return {"target": target, "entries": len(entries), "chars": chars, "limit": limit,
            "pct": round(pct, 1), "max_entry": mx, "trunc": trunc,
            "over": bool(reasons), "reasons": reasons}


def evaluate_session(total: int, threshold: int, caliber: str = "",
                     writer_kind: str = "", present: bool = True) -> Dict[str, Any]:
    """pure 判定：会话水位 = 快照自带 threshold_tokens（不另设阈值）。"""
    pct = (total / threshold * 100) if threshold else 0.0
    reasons: List[str] = []
    if threshold > 0 and total >= threshold:
        reasons.append("total %d >= threshold %d" % (total, threshold))
    return {"present": present, "total": total, "threshold": threshold,
            "pct": round(pct, 1), "caliber": caliber, "writer_kind": writer_kind,
            "over": bool(reasons), "reasons": reasons}




def _set_home(home):
    if home is not None:
        os.environ["MIMIR_AETHER_HOME"] = str(home)


def read_memory_levels(home=None):
    """记忆水位 —— 复用 tools.memory_tool（与 check_memory_hygiene.py 同一实现）。

    -> (rows, error)；数字读不到 ⇒ error（**出声**），不得当 0 静默。
    """
    _set_home(home)
    try:
        from tools.memory_tool import MAX_ENTRY_CHARS, get_memory_store

        store = get_memory_store()
        store.load_from_disk()
    except Exception as exc:
        return None, "memory_tool: %s: %s" % (type(exc).__name__, exc)
    rows = []
    for target in ("memory", "user"):
        try:
            entries = store._entries_for(target)
            cur = store._char_count(target)
            lim = store._char_limit(target)
        except Exception as exc:
            return None, "memory_tool[%s]: %s: %s" % (target, type(exc).__name__, exc)
        rows.append(evaluate_memory_row(target, cur, lim, entries, int(MAX_ENTRY_CHARS)))
    return rows, None


def read_session_level(home=None):
    """会话水位 —— 复用 agent.context_usage_snapshot（prompt_builder 同一真源）。"""
    _set_home(home)
    try:
        from agent.context_usage_snapshot import read_context_usage_snapshot

        snap = read_context_usage_snapshot()
    except Exception as exc:
        return None, "context_usage_snapshot: %s: %s" % (type(exc).__name__, exc)
    if not snap:
        # 快照缺失 != 越阈 != 健康：三态各自明示（present=False），禁当 0 静默。
        return evaluate_session(0, 0, present=False), None
    total = int(snap.get("total_tokens") or snap.get("prompt_tokens") or 0)
    thr = int(snap.get("threshold_tokens") or 0)
    return evaluate_session(total, thr, str(snap.get("caliber") or ""),
                            str(snap.get("writer_kind") or "")), None



def verdict(mem_rows, ses, mem_err, ses_err):
    """pure：折成状态 dict（stdout / --json / selftest 共用，防口径漂移）。"""
    if mem_err or ses_err:
        return {"state": "UNREADABLE", "memory": mem_rows, "session": ses,
                "errors": [e for e in (mem_err, ses_err) if e], "over_items": []}
    over_items = []
    for r in mem_rows or []:
        if r.get("over"):
            over_items.append("memory.%s: %s" % (r["target"], "; ".join(r["reasons"])))
    if ses and ses.get("over"):
        over_items.append("session: %s" % "; ".join(ses["reasons"]))
    return {"state": "OVER" if over_items else "OK", "memory": mem_rows, "session": ses,
            "errors": [], "over_items": over_items}


def ledger_path(home):
    return home / "data" / "ops" / LEDGER_NAME


def append_ledger(path, record):
    """append-only 追加一行；-> None 成功 / 错误串（失败必须出声，不得吞）。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return None
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)


def mark_ledger(s, home, no_ledger=False):
    """越阈 ⇒ 追加台账新行；写失败 ⇒ 状态升 LEDGER_FAIL（出声通路断了）。"""
    if s["state"] != "OVER" or no_ledger:
        return s
    rec = {"ts": time.time(), "date": time.strftime("%Y-%m-%d"), "state": "OVER",
           "over_items": s["over_items"], "memory": s.get("memory"),
           "session": s.get("session"), "pid": os.getpid(), "home": str(home)}
    err = append_ledger(ledger_path(home), rec)
    if err:
        s = dict(s)
        s["state"] = "LEDGER_FAIL"
        s["ledger_error"] = err
    return s



def render(s):
    if s["state"] == "UNREADABLE":
        return "WATER_LEVEL: UNREADABLE errors=%s" % ("; ".join(s["errors"]))
    lines = ["WATER_LEVEL: %s over=%d" % (s["state"], len(s["over_items"]))]
    for r in s.get("memory") or []:
        lines.append("  memory.%s: %d/%d (%.1f%%) max_entry=%d trunc=%d%s" % (
            r["target"], r["chars"], r["limit"], r["pct"], r["max_entry"], r["trunc"],
            "  <== OVER" if r["over"] else ""))
    ses = s.get("session") or {}
    if ses.get("present"):
        lines.append("  session: %d/%d (%.1f%%) caliber=%s%s" % (
            ses.get("total", 0), ses.get("threshold", 0), ses.get("pct", 0.0),
            ses.get("caliber", ""), "  <== OVER" if ses.get("over") else ""))
    else:
        lines.append("  session: 快照缺失（无读数 != 未越阈 != 健康）")
    for item in s["over_items"]:
        lines.append("  -> OVER " + item)
    if s["state"] == "LEDGER_FAIL":
        lines.append("  -> 出声通路断：台账写入失败 %s" % s.get("ledger_error", ""))
    if s["state"] == "OK":
        lines.append("  -> 明示『未越阈』（非静默）")
    return "\n".join(lines)


def rc_for(state):
    return {"OK": RC_OK, "OVER": RC_OVER, "UNREADABLE": RC_UNREADABLE,
            "LEDGER_FAIL": RC_LEDGER_FAIL}[state]


def _default_home():
    try:
        from mimir_constants import get_mimir_home

        return Path(get_mimir_home())
    except Exception:
        return Path(os.path.expanduser("~/.mimiraether"))



def selftest():
    """合成样本（不联盘）· 每个坏病例配孪生对照（禁恒真）。"""
    import tempfile

    cases = []

    def rec(label, want, got):
        cases.append((label, want == got, want, got))

    def _v(mem, ses):
        v = verdict(mem, ses, None, None)
        return "%s:%d" % (v["state"], rc_for(v["state"]))

    # 1 记忆越阈（86% > 85%）-> OVER/rc2；孪生 84% -> OK/rc0
    rec("坏1 记忆 86% -> OVER/rc2", "OVER:2",
        _v([evaluate_memory_row("memory", 6880, 8000, ["x" * 10])], evaluate_session(10, 100)))
    rec("孪1 记忆 84% -> OK/rc0", "OK:0",
        _v([evaluate_memory_row("memory", 6720, 8000, ["x" * 10])], evaluate_session(10, 100)))

    # 2 会话越阈（total == threshold）-> OVER；孪生 299999/300000 -> OK
    rec("坏2 会话 total==threshold -> OVER/rc2", "OVER:2",
        _v([evaluate_memory_row("memory", 100, 8000, ["x"])], evaluate_session(300000, 300000)))
    rec("孪2 会话 299999/300000 -> OK/rc0", "OK:0",
        _v([evaluate_memory_row("memory", 100, 8000, ["x"])], evaluate_session(299999, 300000)))

    # 3 单条目超长（R1 口径）-> OVER；孪生 1200 -> OK
    rec("坏3 单条目 1300>1200 -> OVER/rc2", "OVER:2",
        _v([evaluate_memory_row("memory", 1300, 8000, ["x" * 1300])], evaluate_session(1, 100)))
    rec("孪3 单条目 1200 -> OK/rc0", "OK:0",
        _v([evaluate_memory_row("memory", 1200, 8000, ["x" * 1200])], evaluate_session(1, 100)))

    # 4 读数不可得 -> UNREADABLE/rc3（出声，不得当 0 静默）
    v = verdict(None, None, "memory_tool: boom", None)
    rec("坏4 读数异常 -> UNREADABLE/rc3", "UNREADABLE:3",
        "%s:%d" % (v["state"], rc_for(v["state"])))
    rec("坏4b 必须出声（禁空白静默）", "yes", "yes" if render(v).strip() else "no")

    with tempfile.TemporaryDirectory(prefix="f3_water_selftest_") as td:
        base = Path(td)
        # 5 台账 append-only：越阈两次 -> 行数 1->2（不是覆盖改写）
        oh = base / "overhome"
        lp = ledger_path(oh)
        mark_ledger({"state": "OVER", "over_items": ["x"]}, oh)
        n1 = len(lp.read_text(encoding="utf-8").splitlines())
        mark_ledger({"state": "OVER", "over_items": ["x"]}, oh)
        n2 = len(lp.read_text(encoding="utf-8").splitlines())
        rec("坏5 台账 append-only 行数 +1", "1->2", "%d->%d" % (n1, n2))
        # 6 未越阈不写台账（防噪音）；孪生证明「不写」不是「没跑」
        kh = base / "okhome"
        s_ok = mark_ledger({"state": "OK", "over_items": []}, kh)
        rec("孪6 未越阈不写台账", "OK:nofile", "%s:%s" % (
            s_ok["state"], "file" if ledger_path(kh).exists() else "nofile"))
        # 7 台账写失败 -> LEDGER_FAIL/rc4（出声通路断）
        blocker = base / "blocker"
        blocker.write_text("x", encoding="utf-8")
        s_bad = mark_ledger({"state": "OVER", "over_items": ["x"]}, blocker)
        rec("坏7 台账写失败 -> LEDGER_FAIL/rc4", "LEDGER_FAIL:4",
            "%s:%d" % (s_bad["state"], rc_for(s_bad["state"])))

    ok = True
    for label, good, want, got in cases:
        ok = ok and good
        print("[selftest] %s %s: 期望 %s / 实得 %s" % ("PASS" if good else "FAIL", label, want, got))
    print("[selftest] " + ("ALL PASS" if ok else "HAS FAILURE"))
    return 0 if ok else 1



def main(argv=None):
    ap = argparse.ArgumentParser(description="自身水位阈值出声（F3 第 9 单 · 复用现成读数）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（rc 语义不变）")
    ap.add_argument("--selftest", action="store_true", help="合成样本 + 孪生对照（不联盘）")
    ap.add_argument("--no-ledger", action="store_true", help="只报不记（诊断用）")
    ap.add_argument("--home", default=None, help="覆盖 Mimir 家（受控触发/自证用）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    override = Path(args.home).expanduser() if args.home else None
    home = override if override is not None else _default_home()
    rows, merr = read_memory_levels(override)
    ses, serr = read_session_level(override)
    s = verdict(rows, ses, merr, serr)
    s = mark_ledger(s, home, no_ledger=args.no_ledger)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, sort_keys=True))
    else:
        print(render(s))
    return rc_for(s["state"])


if __name__ == "__main__":
    sys.exit(main())
