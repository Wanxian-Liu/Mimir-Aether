"""IQ-P3-00 baseline parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.iq_p3_evolution_ok_baseline import scan_agent_log


def test_scan_agent_log_ok_pct_excludes_test_sessions():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "agent.log"
        log.write_text(
            "2026-06-01 12:00:00,000 INFO x: post_analysis evolution session_id=iq07-sess applied=1 ok=0\n"
            "2026-06-01 12:00:01,000 INFO x: post_analysis evolution session_id=real-uuid applied=1 ok=1\n"
            "2026-06-01 12:00:02,000 INFO x: post_analysis evolution session_id=real-uuid-2 applied=1 ok=1\n",
            encoding="utf-8",
        )
        stats = scan_agent_log(log, days=30.0, exclude_test_sessions=True)
        assert stats["lines"] == 2
        assert stats["ok_lines"] == 2
        assert stats["ok_pct"] == 100.0


def test_scan_agent_log_including_tests():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "agent.log"
        log.write_text(
            "2026-06-01 12:00:00,000 INFO x: post_analysis evolution session_id=iq07-sess applied=1 ok=0\n"
            "2026-06-01 12:00:01,000 INFO x: post_analysis evolution session_id=real applied=1 ok=1\n",
            encoding="utf-8",
        )
        stats = scan_agent_log(log, days=30.0, exclude_test_sessions=False)
        assert stats["lines"] == 2
        assert stats["ok_lines"] == 1
        assert stats["ok_pct"] == 50.0
