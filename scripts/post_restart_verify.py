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
