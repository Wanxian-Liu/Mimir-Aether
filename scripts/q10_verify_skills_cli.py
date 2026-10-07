#!/usr/bin/env python3
"""Q10 judge - `mimir skills` must import only symbols that exist in this build.

Re-runnable: paste the command, compare the numbers.

    /home/rayliu/src/MimirAether/.venv/bin/python3 scripts/q10_verify_skills_cli.py

Readings: imports=<n>  unresolvable=<m>  controls=pass
rc: 0 = pass (no phantom imports) ; 1 = phantom imports present ; 2 = probe blind

Two-way by construction (a one-way probe that can only say "green" is worthless):
  positive control - the ported symbols MUST resolve
  negative control - a known-unported symbol MUST NOT resolve
"""

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "mimir_cli" / "skills_hub.py"
MODULE = "tools.skills_hub"

# The only hub symbols this repository actually provides.
PORTED = ("HubLockFile", "ensure_hub_dirs")
# Never ported - if these resolve, the probe is looking at the wrong module.
UNPORTED_SENTINEL = "GitHubAuth"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module(MODULE)

    for sym in PORTED:
        if not hasattr(mod, sym):
            print("PROBE-BLIND: ported symbol %r does not resolve" % sym)
            return 2
    if hasattr(mod, UNPORTED_SENTINEL):
        print("PROBE-BLIND: %r resolves but must not; wrong module?" % UNPORTED_SENTINEL)
        return 2

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    total = 0
    bad = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != MODULE:
            continue
        total += 1
        for alias in node.names:
            if not hasattr(mod, alias.name):
                bad += 1
                print("PHANTOM  line %d: %s" % (node.lineno, alias.name))

    print("imports=%d  unresolvable=%d  controls=pass" % (total, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
