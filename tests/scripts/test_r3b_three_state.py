"""R3b three-state passthrough (2026-09-27).

/health exposes `agent` with three values; `insufficient_samples` is the
explicit third state (monitor.get_agent_error_rate_detail) meaning "over
threshold but too few samples to call it an incident".  The probe used to
collapse it into FAIL together with `degraded` -- observed 2026-09-27 as
`R3b FAIL ... insufficient_samples rate=0.1250 max=0.1`: gauge jitter
impersonating an incident.

SUT here is the shell script: the classifier body is extracted from the real
file and executed, plus a control arm running the pre-fix body on the same
payload, so a green arm cannot be inert.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HEALTH = REPO / "scripts" / "mimir_health_check.sh"

SNIPPET_HEAD = "import json, os, sys\nh = json.load(sys.stdin)"
SNIPPET_TAIL = "\n' 2>/dev/null"

PAYLOADS = [
    ("ok", 0, {"status": "ok", "agent": "ok", "agent_error_rate": 0.0,
               "agent_error_reason": "ok", "agent_error_calls": 40,
               "agent_error_min_samples": 20, "agent_tool_p95_ms": 12.0}),
    ("insufficient_samples", 2,
     {"status": "ok", "agent": "insufficient_samples",
      "agent_error_rate": 0.125, "agent_error_reason": "insufficient_samples",
      "agent_error_calls": 8, "agent_error_min_samples": 40,
      "agent_tool_p95_ms": 0.0}),
    ("degraded", 1,
     {"status": "ok", "agent": "degraded",
      "agent_error_rate": 0.5, "agent_error_reason": "rate_above_threshold",
      "agent_error_calls": 200, "agent_error_min_samples": 40,
      "agent_tool_p95_ms": 31.0}),
]

import pytest

# Pre-fix body, verbatim decision: the CONTROL for the differential below.
OLD_FORM = "\n".join([
    "import json, os, sys",
    "h = json.load(sys.stdin)",
    "rate = float(h.get(\"agent_error_rate\") or 0)",
    "agent = h.get(\"agent\", \"ok\")",
    "thresh = float(os.environ.get(\"MIMIR_MONITOR_ERROR_RATE_THRESHOLD\", \"0.10\"))",
    "if agent == \"degraded\" or rate > thresh:",
    "    print(\"collapsed-into-failure\")",
    "    sys.exit(1)",
    "sys.exit(0)",
])


def _live_classifier() -> str:
    src = HEALTH.read_text(encoding="utf-8")
    start = src.index(SNIPPET_HEAD)
    end = src.index(SNIPPET_TAIL, start)
    body = src[start:end]
    assert "insufficient_samples" in body, "extracted body is not the new classifier"
    return body


def _run(tmp_path, name, body, payload):
    f = tmp_path / name
    f.write_text(body, encoding="utf-8")
    r = subprocess.run([sys.executable, str(f)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout


@pytest.mark.parametrize("label,expect,payload", PAYLOADS, ids=[q[0] for q in PAYLOADS])
def test_live_classifier_maps_three_states(tmp_path, label, expect, payload):
    rc, out = _run(tmp_path, "live.py", _live_classifier(), payload)
    assert rc == expect, (label, rc, out)
    assert "reason=" in out and "calls=" in out, out


def test_control_old_form_collapsed_insufficient_into_failure(tmp_path):
    # CONTROL: without the fix the very same payload yields rc 1, so the arm
    # above discriminates the fix instead of being inert.
    rc, out = _run(tmp_path, "old.py", OLD_FORM, PAYLOADS[1][2])
    assert rc == 1, (rc, out)


def test_shell_wires_rc2_to_warn_and_rc1_to_fail():
    text = HEALTH.read_text(encoding="utf-8")
    i = text.index('elif [ "$rc" -eq 2 ]; then')
    assert 'log_result "R3b" "WARN"' in text[i:i + 300], text[i:i + 300]
    assert text.index('log_result "R3b" "FAIL"') > i
