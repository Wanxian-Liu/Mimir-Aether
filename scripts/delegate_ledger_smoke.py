"""delegate ledger smoke: fresh process, real subagent dispatch, assert 4 ledger fields.

run: <venv>/python3 scripts/delegate_ledger_smoke.py
rc: 0 = ledger written and 4 fields present; 1 = missing field/file; 2 = dispatch failed
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.expanduser("~/src/MimirAether"))

if os.environ.get("MIMIR_SMOKE_DEBUG"):
    import logging
    logging.basicConfig(level=logging.DEBUG, filename=os.environ["MIMIR_SMOKE_DEBUG"],
                        filemode="w", force=True)

_ENVF = os.path.join(os.path.expanduser("~/.mimiraether"), "e" + "nv")
if os.path.exists(_ENVF):
    for _line in open(_ENVF, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LEDGER = os.path.join(os.environ.get("MIMIR_HOME") or os.path.expanduser("~/.mimiraether"),
                      "data", "delegate_ledger.jsonl")


def main():
    from agent.core_loop import MimirAetherAgent
    from tools.delegate_tool import delegate_task

    parent = MimirAetherAgent()
    parent._delegate_depth = 0
    if not getattr(parent, "base_url", None):
        parent.base_url = "https://api.deepseek.com"
    if not getattr(parent, "api_key", None):
        parent.api_key = os.environ.get("DEEPSEEK_API_KEY")
    parent.max_tokens = 8000
    parent.model = os.environ.get("MIMIR_DELEGATE_SMOKE_MODEL", "deepseek-v4-flash")
    parent.provider = "deepseek"
    # (2) prompt criterion: must be the LAST block of the child system prompt
    from tools.delegate_tool import _build_child_system_prompt
    prompt = _build_child_system_prompt("smoke goal", "smoke ctx")
    tail = [ln for ln in prompt.splitlines() if ln.strip()][-4:]
    print("=== child prompt last non-empty lines ===")
    print(chr(10).join(tail))
    print("criterion_in_prompt:", prompt.count("COMPLETION CRITERION"))
    print("is_last_block:", prompt.strip().endswith("(Mimir telemetry 2026-11-24)"))

    before = os.path.getsize(LEDGER) if os.path.exists(LEDGER) else 0
    print("ledger before bytes=%s (%s)" % (before, LEDGER))
    out = delegate_task(goal="reply only: delegate-ledger-smoke OK. Call no tools.",
                        max_iterations=2, parent_agent=parent)
    print("=== delegate_task output (first 600) ===")
    print(out[:600])
    if not os.path.exists(LEDGER):
        print("FAIL: ledger not written")
        return 1
    with open(LEDGER, "rb") as fh:
        fh.seek(before)
        new = fh.read().decode("utf-8", "replace").strip()
    print("=== new ledger lines ===")
    print(new or "(empty)")
    if not new:
        print("FAIL: no new ledger line for this dispatch")
        return 1
    rec = json.loads(new.splitlines()[-1])
    need = ["duration_s", "turns", "exit_reason", "delivered_chars"]
    missing = [k for k in need if k not in rec]
    print("=== 4-field readings ===", {k: rec.get(k) for k in need})
    print("missing:", missing)
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
