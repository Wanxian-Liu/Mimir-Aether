#!/usr/bin/env python3
"""check_receipt_selflimit.py -- AGENTS 8.6 self-limit field gate (receipt / completion claim).

WHY THIS EXISTS
  AGENTS 8.5 makes it a hard rule: a blocking clause MUST ship with a runnable
  criterion, otherwise it is a *hint* and MUST NOT be called blocking.
  8.6 (self-limit / abstention) therefore needs a machine-checkable gate.
  This file IS that gate.  Do not treat it as optional tooling.

WHAT IT CHECKS (per input file)
  R1  status line present and value in the fixed four-state set
  R2  coverage line present and non-empty
  R3  uncovered line present and non-empty
  R4  generalisability line present and non-empty
  R5  ABUSE GUARD: if status == abstained, an "attempted" line MUST be present
      and MUST carry a digit.  Abstention without evidence = rejected.
      This is the negative control: it is what stops 8.6 from becoming a
      back door ("I did nothing" dressed up as "I abstained").

USAGE
  python3 scripts/check_receipt_selflimit.py <file> [<file> ...]
  python3 scripts/check_receipt_selflimit.py --selftest     # positive+negative control

EXIT CODES
  0  all files pass          (gate lets through)
  1  at least one file fails (gate blocks)
  2  usage error

Two-way control requirement (AGENTS 9 table tier 4): a gate that only ever
returns 0 is indistinguishable from a broken gate.  Run --selftest to exercise
both the pass path and the block path.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

# Field labels are matched at line start, verbatim, including the full-width colon.
# Renaming / abbreviating them is a contract break: the same labels are used by
# AGENTS 8.4 (receipt contract) and 8.6 (self-limit), and greps rely on them.
STATUS = "\u72b6\u6001:"      # status
COVER = "\u8986\u76d6\u9762:"  # coverage
UNCOVER = "\u672a\u8986\u76d6\u9762:"  # uncovered
GENERAL = "\u53ef\u5916\u63a8\u6027:"  # generalisability
TRIED = "\u5df2\u5c1d\u8bd5:"  # attempted (required only when abstaining)

# Fixed four-state set (AGENTS 8.6). Free-form status text is rejected: the whole
# point is that "did not solve it" becomes a first-class, countable outcome.
STATE_DONE = "\u5df2\u5b8c\u6210"                    # completed
STATE_PART = "\u90e8\u5206\u5b8c\u6210"              # partially completed
STATE_ABSTAIN = "\u672a\u89e3\u51b3\uff08\u5f03\u6743\uff09"  # unresolved (abstained)
STATE_PENDING = "\u5f85\u590d\u6838"                  # awaiting review
STATES = (STATE_DONE, STATE_PART, STATE_ABSTAIN, STATE_PENDING)

_DIGIT = re.compile(r"\d")


def _line(text: str, label: str):
    """Return the value after `label` at line start, or None if absent."""
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith(label):
            return s[len(label):].strip()
    return None


def check_text(text: str):
    """Return (ok, list_of_violations). Pure function -- no IO, no globals."""
    bad = []

    status = _line(text, STATUS)
    if status is None:
        bad.append("R1 missing status line")
    else:
        if not any(status.startswith(s) for s in STATES):
            bad.append("R1 status not in fixed four-state set: %r" % (status,))

    for label, code in ((COVER, "R2"), (UNCOVER, "R3"), (GENERAL, "R4")):
        val = _line(text, label)
        if val is None:
            bad.append("%s missing field" % code)
        elif not val:
            bad.append("%s field present but empty" % code)

    # R5 -- the abuse guard. Only abstention carries the extra burden.
    if status is not None and status.startswith(STATE_ABSTAIN):
        val = _line(text, TRIED)
        if val is None:
            bad.append("R5 abstention without attempted-line (abstention must carry evidence)")
        elif not _DIGIT.search(val):
            bad.append("R5 attempted-line has no digit: %r" % (val,))

    return (not bad), bad


def check_file(path: Path):
    try:
        return check_text(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return False, ["cannot read %s: %s" % (path, exc)]


# --- controls -------------------------------------------------------------
_PASS = "\n".join([
    STATUS + " " + STATE_DONE,
    COVER + " unit tests",
    UNCOVER + " integration",
    GENERAL + " no",
])

_PASS_ABSTAIN = "\n".join([
    STATUS + " " + STATE_ABSTAIN,
    COVER + " read-only survey",
    UNCOVER + " the actual fix",
    GENERAL + " no",
    TRIED + " 7 rounds, 3 forensics",
])

_FAIL_NO_STATUS = "\n".join([
    COVER + " a", UNCOVER + " b", GENERAL + " c",
])

_FAIL_EMPTY = "\n".join([
    STATUS + " " + STATE_DONE, COVER + "", UNCOVER + " b", GENERAL + " c",
])

_FAIL_ABUSE = "\n".join([
    STATUS + " " + STATE_ABSTAIN,
    COVER + " a", UNCOVER + " b", GENERAL + " c",
])

_FAIL_ABUSE_NODIGIT = "\n".join([
    STATUS + " " + STATE_ABSTAIN,
    COVER + " a", UNCOVER + " b", GENERAL + " c", TRIED + " some attempts",
])


def selftest() -> int:
    """Positive + negative control. A gate that never blocks must not pass CI."""
    cases = [
        ("pass/done", _PASS, True),
        ("pass/abstain-with-evidence", _PASS_ABSTAIN, True),
        ("fail/no-status", _FAIL_NO_STATUS, False),
        ("fail/empty-field", _FAIL_EMPTY, False),
        ("fail/abstain-no-tried", _FAIL_ABUSE, False),
        ("fail/abstain-tried-no-digit", _FAIL_ABUSE_NODIGIT, False),
    ]
    rc = 0
    for name, text, expect in cases:
        ok, bad = check_text(text)
        verdict = "OK" if ok == expect else "MISMATCH"
        if ok != expect:
            rc = 1
        print("%-28s expect=%-5s got=%-5s %s%s" % (
            name, expect, ok, verdict, "" if ok else "  <- " + "; ".join(bad)))
    # file path must work too (positive control on real IO)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "r.md"
        p.write_text(_PASS, encoding="utf-8")
        ok, bad = check_file(p)
        print("%-28s expect=%-5s got=%-5s %s" % ("pass/file-io", True, ok,
                                                 "OK" if ok else "MISMATCH"))
        if not ok:
            rc = 1
    print("selftest rc=%d" % rc)
    return rc


def main(argv) -> int:
    args = argv[1:]
    if not args:
        sys.stderr.write(__doc__)
        return 2
    if args[0] == "--selftest":
        return selftest()

    failed = 0
    for name in args:
        path = Path(name)
        ok, bad = check_file(path)
        if ok:
            print("PASS %s" % path)
        else:
            failed += 1
            print("FAIL %s" % path)
            for b in bad:
                print("     - %s" % b)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
