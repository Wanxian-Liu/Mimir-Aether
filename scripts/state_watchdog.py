#!/usr/bin/env python3
"""N13 段1 · 看门狗（沉默检测 · 只检测/报警 · **不改任何卡的 state**）

来源：四方会议卡 L736 转移表 T8 + L753-757 三件最小实现 ③ + L772/L773 判据两向。
T8（L747）任意 LIVE 态 --deadline_exceeded--> stalled 的**检测半**（本段）；
改卡状态（stalled 落盘）属段 2 —— 本脚本只读卡、只写自己的 ledger/报警文件。

规则（E3 · L721）：
    ∀ 卡： now − last_event_at ≤ deadline  ∨  state == stalled
    即「每一张卡要么在动、要么已被标为停摆」——不存在「不知道在不在动」的第三态。

  last_event_at 来源 = state-events.jsonl（唯一事件真源）—— 无需额外计时器（L756）。
  deadline 来源 = ① 卡内 `deadline:` 字段 ② 否则 state 默认表（DEFAULT_DEADLINES）；
                 awaiting_decision / awaiting_human 属「等人」态，**不给 deadline**
                 ⇒ 永不判停摆（等人不是停摆）。

输出（stdout · 逐行可 grep）：
    stalled: card_id=<id> state=<s> silent_s=<n> deadline_s=<d> last_event_at=<iso>
    alert: STALLED card_id=<id> event=deadline_exceeded to=stalled notify=orchestrator
    summary: scanned=<n> live=<n> stalled=<n> alerts=<n> unbaselined=<n> already_stalled=<n> heartbeat=<path>
报警清单落盘：state-alerts.jsonl（每行一条 JSON · append-only）
心跳落盘：watchdog-heartbeat.json（tick 递增）；外层发现 = --check-heartbeat（rc 语义）

用法：
    python3 scripts/state_watchdog.py                     # 真跑一 tick
    python3 scripts/state_watchdog.py --selftest          # L772 正控 + L773 负控（两向）
    python3 scripts/state_watchdog.py --check-heartbeat   # rc=0 新鲜 / rc=1 缺失或过期
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_event_log import last_event_map  # noqa: E402

LIVE_STATES = {
    "pending", "in_progress", "awaiting_verify", "awaiting_decision",
    "awaiting_orchestrator", "awaiting_human", "stalled",
}

# state -> deadline 秒。None = 不给 deadline（等人态 / 已标记态）。
# 口径（卡 L833）：具体数值须 per-线 实测后调 —— 这里是**初始值**，可被
# <data>/state-watchdog-deadlines.json 覆盖（不改代码即可调参）。
DEFAULT_DEADLINES = {
    "pending": 24 * 3600,
    "in_progress": 2 * 3600,
    "awaiting_verify": 4 * 3600,
    "awaiting_orchestrator": 3600,
    "awaiting_decision": None,
    "awaiting_human": None,
    "stalled": None,
}

# 数据根解析顺序与 gateway 同源（mimir_constants.get_mimir_home）：
#   MIMIR_AETHER_HOME → MIMIRAETHER_HOME → ~/.mimiraether
# 全用**绝对根**、不依赖 cwd；解析错会**出声**（见 preflight_guard）——
# 若静默扫到 0 张卡，脚本会假装「一切正常」（正是要防的静默失败家族）。
def _home():
    v = os.environ.get("MIMIR_AETHER_HOME") or os.environ.get("MIMIRAETHER_HOME")
    return v.strip() if v and v.strip() else os.path.expanduser("~/.mimiraether")


def _wiki():
    v = os.environ.get("MIMIR_WIKI_HOME")
    return v.strip() if v and v.strip() else os.path.expanduser("~/wiki")


DATA_DIR = os.path.join(_home(), "data")
DEFAULT_LEDGER = os.path.join(_wiki(), "discussions/2026-10-08-NEW阶段-活卡状态机.md")
DEFAULT_EVENTS = os.path.join(DATA_DIR, "state-events.jsonl")
DEFAULT_ALERTS = os.path.join(DATA_DIR, "state-alerts.jsonl")
DEFAULT_HEARTBEAT = os.path.join(DATA_DIR, "watchdog-heartbeat.json")
DEFAULT_DEADLINE_OVERRIDE = os.path.join(DATA_DIR, "state-watchdog-deadlines.json")

_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n?```", re.S)


def parse_duration(v):
    """'30m'/'2h'/'90s'/'1d'/3600/'' -> 秒（None = 无 deadline）。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().strip("'\"")
    if not s:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd]?)", s)
    if not m:
        return None
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def parse_cards(ledger_path):
    """扫台账 yaml 卡块 -> [{card_id, state, deadline_raw, owner, line}]。

    单一真源口径：只认卡内顶格 `state:` 字段（唯一权威 · L755）。本项目不引 yaml
    依赖 —— 只解顶格键值，块内缩进行属细节、本脚本不解析。
    """
    if not os.path.exists(ledger_path):
        return []
    text = open(ledger_path, encoding="utf-8").read()
    cards = []
    for m in _BLOCK_RE.finditer(text):
        line_no = text[: m.start()].count("\n") + 1
        kv = {}
        for ln in m.group(1).split("\n"):
            if not ln or ln[0] in " \t#-":
                continue
            if ":" not in ln:
                continue
            k, _, v = ln.partition(":")
            kv[k.strip()] = v.strip().strip("'\"")
        cid = kv.get("id", "")
        if not re.fullmatch(r"N\d+\w*", cid or ""):
            continue
        cards.append({
            "card_id": cid,
            "state": kv.get("state", ""),
            "deadline_raw": kv.get("deadline", ""),
            "owner": kv.get("owner", ""),
            "line": line_no,
        })
    return cards


def load_deadlines(override_path=None):
    table = dict(DEFAULT_DEADLINES)
    p = override_path or DEFAULT_DEADLINE_OVERRIDE
    if p and p != "/nonexistent.json" and os.path.exists(p):
        try:
            for k, v in json.load(open(p, encoding="utf-8")).items():
                table[k] = parse_duration(v)
        except (json.JSONDecodeError, OSError):
            pass
    return table


def deadline_for(card, defaults):
    d = parse_duration(card.get("deadline_raw"))
    return d if d is not None else defaults.get(card.get("state"))
def preflight_guard(ledger, cards):
    """前置闸（出声）：配置错 ⇒ 冒泡，绝不静默报「无事」。

    防的事故：HOME 解析错 / 台账改名 ⇒ 扫到 0 张卡，输出「stalled=0」假装绿。
    返回 (rc, message)；rc=0 过闸。
    """
    if not os.path.exists(ledger):
        return 2, "ERROR: ledger not found: %s" % ledger
    if not cards:
        return 3, ("ERROR: scanned=0 cards (ledger=%s) — 路径/格式错，拒绝静默报绿"
                   % ledger)
    return 0, "preflight ok: cards=%d" % len(cards)


def tick(*, ledger, events, alerts, heartbeat, now=None, deadline_override=None):
    """跑一 tick。返回 dict（含 stdout 行 + 读数）。**只读卡**（不写任何卡文件）。"""
    t0 = time.time()
    now = time.time() if now is None else now
    defaults = load_deadlines(deadline_override)
    cards = parse_cards(ledger)
    evmap = last_event_map(events)

    lines, alert_recs = [], []
    n_live = n_stalled = n_unbase = n_already = 0
    unbase_ids = []
    for c in cards:
        st = c["state"]
        if st not in LIVE_STATES:
            continue
        n_live += 1
        lea = evmap.get(c["card_id"])
        if lea is None:
            n_unbase += 1          # 无事件基线 ⇒ 算不出沉默（不冒充读数）
            unbase_ids.append(c["card_id"])
            continue
        dl = deadline_for(c, defaults)
        if dl is None:
            continue
        silent = now - lea
        if st == "stalled":
            n_already += 1         # 已标记 ⇒ 不重复报警（防告警洪水）
            continue
        if silent > dl:
            n_stalled += 1
            lines.append(
                "stalled: card_id=%s state=%s silent_s=%d deadline_s=%d last_event_at=%s"
                % (c["card_id"], st, int(silent), int(dl),
                   time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(lea))))
            lines.append(
                "alert: STALLED card_id=%s event=deadline_exceeded to=stalled notify=orchestrator"
                % c["card_id"])
            alert_recs.append({
                "ts": now, "card_id": c["card_id"], "kind": "STALLED",
                "event": "deadline_exceeded", "from": st, "to": "stalled",
                "silent_s": int(silent), "deadline_s": int(dl),
                "last_event_at": lea, "notify": "orchestrator",
                "actor": "watchdog", "trace_id": "n13-watchdog",
            })

    if alert_recs:
        d = os.path.dirname(alerts)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(alerts, "a", encoding="utf-8") as fh:
            for rec in alert_recs:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    prev_tick = 0
    if os.path.exists(heartbeat):
        try:
            prev_tick = int(json.load(open(heartbeat, encoding="utf-8")).get("tick", 0))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            prev_tick = 0
    hb = {
        "ts": now, "tick": prev_tick + 1, "pid": os.getpid(),
        "scanned": len(cards), "live": n_live, "stalled": n_stalled,
        "alerts": len(alert_recs), "unbaselined": n_unbase,
        "already_stalled": n_already, "duration_ms": int((time.time() - t0) * 1000),
        "ledger": ledger, "events": events, "alerts_path": alerts,
    }
    d = os.path.dirname(heartbeat)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = heartbeat + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(hb, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, heartbeat)      # 原子替换：读者永不见半份心跳

    lines.append(
        "summary: scanned=%d live=%d stalled=%d alerts=%d unbaselined=%d "
        "already_stalled=%d heartbeat=%s"
        % (len(cards), n_live, n_stalled, len(alert_recs), n_unbase, n_already, heartbeat))
    lines.append("unbaselined: ids=%s" % (",".join(unbase_ids[:12]) if unbase_ids else "-"))
    return {"lines": lines, "heartbeat": hb, "alerts": alert_recs, "cards": cards}


def check_heartbeat(path, max_age_s, now=None):
    """外层发现入口：心跳缺失/过期 ⇒ rc=1（供 systemd timer / 外部日报 / health_check 调）。"""
    now = time.time() if now is None else now
    if not os.path.exists(path):
        return 1, "heartbeat MISSING: %s" % path
    try:
        hb = json.load(open(path, encoding="utf-8"))
        age = now - float(hb["ts"])
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as e:
        return 1, "heartbeat UNREADABLE: %r" % (e,)
    if age > max_age_s:
        return 1, "heartbeat STALE: age_s=%d > max_age_s=%d tick=%s" % (
            int(age), max_age_s, hb.get("tick"))
    return 0, "heartbeat OK: age_s=%d tick=%s stalled=%s" % (
        int(age), hb.get("tick"), hb.get("stalled"))


_MOCK_LEDGER = """---
title: mock
---

```yaml
id: {cid}
title: mock card
state: {state}
owner: hermes
{deadline_line}```
"""

_MOCK2 = "```yaml\nid: {cid}\ntitle: ok\nstate: in_progress\nowner: hermes\n```\n"

MOCK_NOW = 1791500000.0


def _arm(td, *, primary_state, primary_age_s, extra_card=None,
         extra_card_baseline=True, primary_deadline="deadline: 1h\n", deadline_override=None):
    """构造 mock 环境并跑一 tick。primary_age_s = now − last_event_at。"""
    from state_event_log import append_event
    ledger = os.path.join(td, "ledger.md")
    events = os.path.join(td, "state-events.jsonl")
    alerts = os.path.join(td, "state-alerts.jsonl")
    hb = os.path.join(td, "watchdog-heartbeat.json")
    body = _MOCK_LEDGER.format(cid="N901", state=primary_state,
                               deadline_line=primary_deadline)
    if extra_card:
        body += "\n" + _MOCK2.format(cid=extra_card)
    open(ledger, "w", encoding="utf-8").write(body)
    append_event({"card_id": "N901", "from": "pending", "to": primary_state,
                  "event": "deps_all_closed", "actor": "hermes", "trace_id": "t-mock"},
                 path=events, ts=MOCK_NOW - primary_age_s)
    if extra_card and extra_card_baseline:
        append_event({"card_id": extra_card, "from": "pending", "to": "in_progress",
                      "event": "deps_all_closed", "actor": "hermes", "trace_id": "t-mock"},
                     path=events, ts=MOCK_NOW)
    r = tick(ledger=ledger, events=events, alerts=alerts, heartbeat=hb, now=MOCK_NOW,
             deadline_override=deadline_override or "/nonexistent.json")
    r["alerts_path"] = alerts
    return r


def _count(lines, prefix):
    return sum(1 for ln in lines if ln.startswith(prefix))


def selftest():
    """L772 正控 + L773 负控（两向）+ 附带负控（等人态不误报）。rc=0 全过 / rc=1 拦。"""
    import tempfile
    from state_event_log import line_count
    ok = True

    print("== L772 正控：last_event_at = now − 2×deadline ⇒ 期望 1 行 stalled + 1 行报警 ==")
    with tempfile.TemporaryDirectory() as td:
        r = _arm(td, primary_state="in_progress", primary_age_s=2 * 3600.0,   # deadline=1h ⇒ 2×deadline
                 extra_card="N902")   # N902 沉默=0（不该报）
        for ln in r["lines"]:
            print(ln)
        st, al = _count(r["lines"], "stalled:"), _count(r["lines"], "alert:")
        good = st == 1 and al == 1 and r["heartbeat"]["stalled"] == 1 and line_count(r["alerts_path"]) == 1
        print("[L772 正控] stalled=%d alert=%d hb.stalled=%s alerts_lines=%d -> %s"
              % (st, al, r["heartbeat"]["stalled"], line_count(r["alerts_path"]),
                 "PASS" if good else "FAIL"))
        ok = ok and good

    print("== L773 负控：last_event_at = now ⇒ 期望 0 行 stalled ==")
    with tempfile.TemporaryDirectory() as td:
        r = _arm(td, primary_state="in_progress", primary_age_s=0.0)
        for ln in r["lines"]:
            print(ln)
        st, al = _count(r["lines"], "stalled:"), _count(r["lines"], "alert:")
        good = st == 0 and al == 0 and r["heartbeat"]["stalled"] == 0 and line_count(r["alerts_path"]) == 0
        print("[L773 负控] stalled=%d alert=%d hb.stalled=%s alerts_lines=%d -> %s"
              % (st, al, r["heartbeat"]["stalled"], line_count(r["alerts_path"]),
                 "PASS" if good else "FAIL"))
        ok = ok and good

    print("== 附带负控：等人态 awaiting_decision 无 deadline ⇒ 沉默 365 天也不报 ==")
    with tempfile.TemporaryDirectory() as td:
        r = _arm(td, primary_state="awaiting_decision", primary_age_s=365 * 86400.0,
                 primary_deadline="")   # 卡不带 deadline ⇒ 落到 state 默认表（等人态=None）
        for ln in r["lines"]:
            print(ln)
        st = _count(r["lines"], "stalled:")
        good = st == 0 and r["heartbeat"]["stalled"] == 0
        print("[等人态负控] stalled=%d -> %s" % (st, "PASS" if good else "FAIL"))
        ok = ok and good

    print("== 附带负控：无事件基线的卡 ⇒ 计入 unbaselined，不冒充 stalled ==")
    with tempfile.TemporaryDirectory() as td:
        r = _arm(td, primary_state="pending", primary_age_s=0.0,
                 extra_card="N904", extra_card_baseline=False)
        st = _count(r["lines"], "stalled:")
        good = st == 0 and r["heartbeat"]["unbaselined"] == 1
        print("[无基线] stalled=%d unbaselined=%s -> %s"
              % (st, r["heartbeat"]["unbaselined"], "PASS" if good else "FAIL"))
        ok = ok and good

    print("== 附带正控：--check-heartbeat 对新鲜心跳 rc=0 / 对缺失 rc=1 ==")
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        p = os.path.join(td, "hb.json")
        rc_missing, msg_m = check_heartbeat(p, 900)
        json.dump({"ts": MOCK_NOW, "tick": 3}, open(p, "w"))
        rc_fresh, msg_f = check_heartbeat(p, 900, now=MOCK_NOW + 10)
        rc_stale, msg_s = check_heartbeat(p, 900, now=MOCK_NOW + 5000)
        print("[心跳] missing rc=%d (%s) | fresh rc=%d (%s) | stale rc=%d (%s)"
              % (rc_missing, msg_m, rc_fresh, msg_f, rc_stale, msg_s))
        good = rc_missing == 1 and rc_fresh == 0 and rc_stale == 1
        print("[心跳 两向] -> %s" % ("PASS" if good else "FAIL"))
        ok = ok and good

    print("[selftest] rc=%d" % (0 if ok else 1))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="N13 看门狗（沉默检测 · 只检测/报警）")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--events", default=DEFAULT_EVENTS)
    ap.add_argument("--alerts", default=DEFAULT_ALERTS)
    ap.add_argument("--heartbeat", default=DEFAULT_HEARTBEAT)
    ap.add_argument("--deadline-override", default=DEFAULT_DEADLINE_OVERRIDE)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check-heartbeat", action="store_true")
    ap.add_argument("--max-age", type=float, default=900.0,
                    help="心跳新鲜度上限秒（默认 900 = 3×5min tick 周期）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.check_heartbeat:
        rc, msg = check_heartbeat(args.heartbeat, args.max_age)
        print(msg)
        return rc
    r = tick(ledger=args.ledger, events=args.events, alerts=args.alerts,
             heartbeat=args.heartbeat, deadline_override=args.deadline_override)
    for ln in r["lines"]:
        print(ln)
    rc, msg = preflight_guard(args.ledger, r["cards"])
    if rc:
        print(msg)
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
