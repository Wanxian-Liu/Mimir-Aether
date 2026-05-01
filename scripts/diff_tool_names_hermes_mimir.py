#!/usr/bin/env python3
"""
Compare OpenAI tool *names* exposed by Hermes vs MimirAether (after each repo's discovery).

Hermes: ``model_tools.get_tool_definitions(quiet_mode=True)`` (default = all toolsets).
Mimir: ``tools.registry.registry`` after ``import model_tools`` (triggers ``_discover_tools``).

Each side runs in a **fresh Python subprocess** so ``tools.*`` / ``model_tools`` do not clash.

Usage:
  python scripts/diff_tool_names_hermes_mimir.py \\
      --hermes-root /path/to/hermes-agent \\
      --mimir-root  /path/to/MimirAether

Env (optional):
  HERMES_ROOT, MIMIR_ROOT — see --help defaults

Exit code: 0 if sets match, 1 if they differ, 2 on subprocess failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def _names_via_subprocess(repo_root: str, kind: str) -> list[str]:
    if kind == "hermes":
        code = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from model_tools import get_tool_definitions
defs = get_tool_definitions(quiet_mode=True)
names = sorted({
    t["function"]["name"]
    for t in defs
    if t.get("function", {}).get("name")
})
print(json.dumps(names))
"""
    elif kind == "mimir":
        code = r"""
import json, sys, importlib
sys.path.insert(0, sys.argv[1])
importlib.import_module("model_tools")
from tools.registry import registry
print(json.dumps(sorted(registry.get_all_tool_names())))
"""
    else:
        raise ValueError(kind)

    proc = subprocess.run(
        [sys.executable, "-c", code, repo_root],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{kind} subprocess exit {proc.returncode}\n{proc.stderr or proc.stdout}"
        )
    line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    return json.loads(line)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--hermes-root",
        default=os.environ.get("HERMES_ROOT", "/home/rayliu/.openclaw/projects/hermes-agent"),
        help="Hermes checkout at docs/hermes_mimir_behavior_matrix.md HERMES_REF",
    )
    p.add_argument(
        "--mimir-root",
        default=os.environ.get(
            "MIMIR_ROOT",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ),
        help="MimirAether repo root (default: parent of scripts/)",
    )
    p.add_argument("--json", action="store_true", help="Emit one JSON object to stdout")
    args = p.parse_args()

    hermes_root = os.path.abspath(args.hermes_root)
    mimir_root = os.path.abspath(args.mimir_root)

    try:
        h = set(_names_via_subprocess(hermes_root, "hermes"))
        m = set(_names_via_subprocess(mimir_root, "mimir"))
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 2

    only_h = sorted(h - m)
    only_m = sorted(m - h)

    if args.json:
        print(
            json.dumps(
                {
                    "hermes_root": hermes_root,
                    "mimir_root": mimir_root,
                    "hermes_only": only_h,
                    "mimir_only": only_m,
                    "intersection": sorted(h & m),
                },
                indent=2,
            )
        )
    else:
        print(f"Hermes tools: {len(h)}  Mimir tools: {len(m)}  intersection: {len(h & m)}")
        if only_h:
            print(f"\nOnly in Hermes ({len(only_h)}):")
            for n in only_h:
                print(f"  + {n}")
        if only_m:
            print(f"\nOnly in Mimir ({len(only_m)}):")
            for n in only_m:
                print(f"  - {n}")
        if not only_h and not only_m:
            print("\nTool name sets match.")

    return 0 if not only_h and not only_m else 1


if __name__ == "__main__":
    raise SystemExit(main())
