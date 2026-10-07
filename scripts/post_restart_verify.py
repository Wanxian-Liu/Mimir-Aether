"""post_restart_verify.py - post-restart verifier (exit-history + close-phase + cron).

Promoted from tmp/post_restart_verify_v2.py (2026-09-28). Two fixes over v2:
  1. Startup logs use logger `__main__` -> they land in agent.log / errors.log,
     NOT gateway.log. v2 read only gateway.log and reported a false 0.
  2. The cascade window is bounded by THIS process start time; a fixed tail-N
     window can silently exclude the very burst it is meant to measure.

Usage
  python3 scripts/post_restart_verify.py          # read-only verdicts (default)
  python3 scripts/post_restart_verify.py --fix    # also recompute empty cron next_run_at
  python3 scripts/post_restart_verify.py --json   # machine-readable

Verdicts (VERDICT: PASS only if no FAIL)
  J1 service ActiveState == active
  J2 enabled cron jobs with empty next_run_at == 0   (--fix repairs)
  J3 exit table has >= 1 row
  J4 close-phase cascade markers since process start == 0
  J5 evidence of the startup reconcile call -> WARN only (not FAIL) until the
     unconditional "Exit reconcile ran" line lands on a restarted process
  J6 cap and peak have separated: room = cap - current >= 2 GiB (absolute),
     with a censored-peak hint (memory.peak pinned at a whole GiB means it
     was clamped at the cap it lived under, so it alone is not evidence)

Exit: 0 PASS / 1 FAIL / 2 execution error.
"""

from __future__ import annotations

import argparse, datetime, json, os, pathlib, subprocess, sys


def _resolve_home() -> pathlib.Path:
    """Runtime data root without the $HOME double-nesting trap.

    Same contract as scripts/run_mech_checks.py, and no absolute home path may
    be committed (pre-push gate A6: home-path shapes are immutable evidence).
    """
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "MIMIR_HOME"):
        v = os.getenv(key, "").strip()
        if v:
            return pathlib.Path(v).expanduser()
    h = pathlib.Path.home()
    if h.name == ".mimiraether":
        return h
    return h / ".mimiraether"


HOME = _resolve_home()
REPO = pathlib.Path(__file__).resolve().parents[1]
UNIT = "mimiraether.service"
CASCADE_PATTERNS = (
    "Event loop is closed", "Bad file descriptor", "meta_path",
    "Task was destroyed", "send_data",
)
RECONCILE_NEEDLES = ("exit reconcile ran", "previous gateway exit record", "exit_history")

fails: list = []
warns: list = []


def sh(cmd: str, timeout: int = 40) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()
    except Exception as exc:
        return "ERR:%s" % exc


def sc(prop: str) -> str:
    return sh("systemctl --user show %s -p %s --value" % (UNIT, prop))


def log_lines(name: str) -> list:
    f = HOME / "logs" / name
    if not f.exists():
        return []
    return f.read_text(errors="replace").splitlines()


def start_prefix() -> tuple:
    """(prefix YYYY-MM-DD HH:MM:SS | None, raw timestamp, start datetime | None).

    The systemd `%Z` is the LOCAL zone and unit logs are stamped in local wall
    clock, so the stamp is parsed as a naive local datetime. Forcing tzinfo=UTC
    and then calling astimezone() shifted the boundary +8h (08:34 instead of
    00:34) and made every record fall out of scope -- i.e. an empty window that
    still printed cascade=0, a false PASS (2026-09-28).
    """
    raw = sc("ExecMainStartTimestamp")
    for fmt in ("%a %Y-%m-%d %H:%M:%S %Z", "%a %Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S"), raw, dt
        except Exception:
            continue
    return None, raw, None


def _opens_record(l: str) -> bool:
    """True only for a line that starts with a `YYYY-MM-DD HH:MM:SS` stamp."""
    return (len(l) >= 19 and l[4] == "-" and l[7] == "-" and l[10] == " "
            and l[13] == ":" and l[16] == ":" and l[0:4].isdigit()
            and l[5:7].isdigit() and l[8:10].isdigit())


def in_scope(lines: list, prefix) -> tuple:
    """Records at/after process start. Falls back to tail-400 and says so.

    Only timestamped lines open a record. A traceback body / continuation line
    carries no timestamp and starts with message text, so a naive
    ``l[:19] >= prefix`` string compare counts it as "in scope" whenever that
    text sorts above a digit (e.g. 'I' > '2') -- that produced a false
    FAIL=47 on 2026-09-28 by counting 09-27 bodies. Bodies now inherit the
    scope of their parent record.
    """
    if prefix is None:
        return lines[-400:], "tail400-fallback(no-start-time)"
    out = []
    active = False
    for l in lines:
        if _opens_record(l):
            active = l[:19] >= prefix
        if active:
            out.append(l)
    return out, "since-start"


def check_active() -> str:
    st = sc("ActiveState")
    ok = st == "active"
    if not ok:
        fails.append("J1 ActiveState=%s" % st)
    return "J1 active=%s pid=%s nrestart=%s" % (st, sc("MainPID"), sc("NRestarts"))


def check_cron(fix: bool) -> str:
    sys.path.insert(0, str(REPO))
    from cron import jobs as cj
    fixed, still = [], []
    for j in cj.load_jobs():
        if not j.get("enabled", True) or j.get("next_run_at"):
            continue
        nxt = cj.compute_next_run(j.get("schedule") or {})
        if nxt and fix:
            cj.update_job(j["id"], {"next_run_at": nxt})
            fixed.append(j["id"])
        else:
            still.append(j["id"])
    ens = [j for j in cj.load_jobs() if j.get("enabled", True)]
    nulls = [j["id"] for j in ens if not j.get("next_run_at")]
    if nulls:
        fails.append("J2 enabled-with-null-next_run_at=%d %s" % (len(nulls), nulls))
    return ("J2 enabled=%d null=%d repaired=%d still=%d"
            % (len(ens), len(nulls), len(fixed), len(still)))


def check_exit_table() -> str:
    f = HOME / "data" / "ops" / "gateway_exit_history.jsonl"
    rows = [l for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
    if not rows:
        fails.append("J3 exit table empty")
    tail = rows[-1][:150] if rows else "-"
    return "J3 rows=%d last=%s" % (len(rows), tail)


def check_cascade() -> str:
    prefix, raw, dt = start_prefix()
    lines, mode = in_scope(log_lines("gateway.log"), prefix)
    hits = {pat: sum(1 for l in lines if pat in l) for pat in CASCADE_PATTERNS}
    total = sum(hits.values())
    uptime = (datetime.datetime.now() - dt).total_seconds() if dt else 0.0
    if dt is None:
        # Unknown boundary => the window is the weak tail-400 fallback, which
        # can silently exclude the burst it is meant to measure. Never silent.
        warns.append("J4 boundary unknown (start stamp unparseable); window=%s" % mode)
    if not lines and uptime > 120:
        # No discriminating power: an empty window cannot certify "no cascade".
        fails.append("J4 empty-scope uptime=%.0fs (boundary filter broken?)" % uptime)
    if total:
        fails.append("J4 cascade-since-start=%d %s" % (total, hits))
    return ("J4 scope=%s lines=%d start=%s uptime=%.0fs cascade=%d %s"
            % (mode, len(lines), raw, uptime, total, hits))


def check_reconcile() -> str:
    prefix, _raw, _dt = start_prefix()
    found = []
    for name in ("gateway.log", "agent.log", "errors.log"):
        lines, _m = in_scope(log_lines(name), prefix)
        for l in lines:
            low = l.lower()
            if any(n in low for n in RECONCILE_NEEDLES):
                found.append("[%s] %s" % (name, l[:150]))
    if not found:
        warns.append("J5 no reconcile trace since start (unconditional line lands next restart)")
    return "J5 trace_lines=%d %s" % (len(found), found[-1] if found else "")


# --- F-2 (#14) memory headroom: peak-vs-cap separation -----------------------
# Why a gate and not a note: on 2026-10-05 the 4G->6G relief was written, then
# reverted, and nothing failed -- the cap stayed glued to the high-water mark
# (memory.peak == memory.max == 4294967296) with no alarm. A silent revert of
# this fix is indistinguishable from the bug it fixes, so it gets a verdict.
# Two criteria, in priority order (I-4, 2026-10-07 Liu-approved).
#   PRIMARY  room_peak = cap - peak > 0   -> "cap and peak have separated".
#     This is the only *relative* term here and it does NOT violate the older
#     "relative terms banned" note: that ban was about ``peak`` as SOLE
#     evidence -- a peak clamped at the cap it lived under is a censored lower
#     bound, so cap-vs-peak could be fooled while a live workload sat at the
#     cap. It bans (peak as evidence), not (cap vs peak as a separation
#     check). Once the cap is raised the separation IS the assertion, and peak
#     is monotone (never decreases) -> cannot flicker.
#   FALLBACK room_now = cap - current >= F2_MIN_NOW_ROOM_BYTES (1 GiB).
#     ``current`` cannot be clamped by a cap (uncensored) but tracks load: at
#     the 6 GiB cap the live range is ~3.8-4.0 GiB => room_now 2.00-2.18 GiB,
#     so a 2 GiB floor flapped red/green *at the operating point* (I-4:
#     room_now=2323361792 PASS vs 2.00e9 FAIL). 1 GiB = genuinely low
#     headroom, demoted to a backstop.
F2_MIN_NOW_ROOM_BYTES = 1 * 1024 ** 3   # fallback floor on cap-current
F2_MIN_ROOM_BYTES = F2_MIN_NOW_ROOM_BYTES   # legacy alias (callers/tests)
GIB = 1024 ** 3


def memory_headroom(live_cap, peak, current, min_room=F2_MIN_NOW_ROOM_BYTES):
    """Pure verdict for "cap and peak have separated" -> (ok, detail dict).

    Inputs are kernel cgroup readings in bytes; None means the kernel said
    "max" (no limit). Criteria (module notes above):
      * PRIMARY  ``room_peak > 0``        -- cap/peak separation, monotone
      * FALLBACK ``room_now >= min_room`` -- live headroom, uncensored
    ``verdict_reason`` names which criterion decided: a bare ok=False cannot
    tell a demoted fallback apart from a re-glued cap (forensics).
    """
    def g(x):
        return "max" if x is None else int(x)

    if live_cap is None:
        return True, {"cap": "max", "peak": g(peak), "current": g(current),
                      "room_now": "inf", "room_peak": "inf", "censored": False,
                      "why": "cap=unbounded", "verdict_reason": "cap-unbounded"}
    room_now = int(live_cap) - int(current or 0)
    room_peak = int(live_cap) - int(peak or 0)
    censored = bool(peak) and int(peak) % GIB == 0
    ok_peak = room_peak > 0
    ok_now = room_now >= min_room
    ok = ok_peak and ok_now
    if ok_peak and ok_now:
        reason = "room_peak=%d>0 and room_now=%d>=%d" % (room_peak, room_now, min_room)
    elif not ok_peak and not ok_now:
        reason = "room_peak=%d<=0 (cap glued to peak) and room_now=%d<%d" % (
            room_peak, room_now, min_room)
    elif not ok_peak:
        reason = "room_peak=%d<=0 (cap glued to peak; fallback ok)" % room_peak
    else:
        reason = "room_now=%d<%d (fallback; cap/peak separated room_peak=%d)" % (
            room_now, min_room, room_peak)
    return ok, {"cap": int(live_cap), "peak": g(peak), "current": g(current),
                "room_now": room_now, "room_peak": room_peak,
                "censored": censored, "min_room": min_room,
                "ok_peak": ok_peak, "ok_now": ok_now,
                "verdict_reason": reason}


def check_memory_headroom() -> str:
    """J6 live readings: kernel cgroup cap vs real peak vs current."""
    cg = sc("ControlGroup")
    base = pathlib.Path("/sys" + "/fs/cgroup") / cg.lstrip("/")

    def read(name):
        try:
            v = (base / name).read_text().strip()
        except Exception as exc:
            return "ERR:%s" % exc
        if v == "max":
            return None
        try:
            return int(v)
        except ValueError:
            return "ERR:not-int:%s" % v

    cap = read("memory.max")
    peak = read("memory.peak")
    cur = read("memory.current")
    if isinstance(cap, str) or isinstance(peak, str) or isinstance(cur, str):
        fails.append("J6 unreadable kernel readings cap=%s peak=%s current=%s"
                     % (cap, peak, cur))
        return "J6 cap=%s peak=%s current=%s" % (cap, peak, cur)
    ok, detail = memory_headroom(cap, peak, cur)
    if not ok:
        fails.append("J6 no-headroom %s" % detail)
    return "J6 ok=%s %s" % (ok, detail)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="post-restart verifier")
    ap.add_argument("--fix", action="store_true", help="recompute empty cron next_run_at")
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    a = ap.parse_args(argv)
    rows = []
    try:
        rows.append(check_active())
        rows.append(check_cron(a.fix))
        rows.append(check_exit_table())
        rows.append(check_cascade())
        rows.append(check_reconcile())
        rows.append(check_memory_headroom())
    except Exception as exc:
        print("VERDICT: FAIL")
        print("error: %r" % (exc,))
        return 2
    verdict = "FAIL" if fails else "PASS"
    if a.json:
        print(json.dumps({"verdict": verdict, "rows": rows, "warns": warns, "fails": fails},
                         ensure_ascii=False))
    for r in rows:
        print(r)
    for w in warns:
        print("WARN: " + w)
    for fl in fails:
        print("FAIL: " + fl)
    print("VERDICT: " + verdict)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
