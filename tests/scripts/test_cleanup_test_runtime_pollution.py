"""cleanup_test_runtime_pollution.py"""

from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.cleanup_test_runtime_pollution import _filter_agent_log, _remove_test_skills


def test_filter_agent_log_strips_synthetic_sessions():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "agent.log"
        log.write_text(
            "2026-06-01 12:00:00,000 INFO x: post_analysis evolution session_id=iq07-sess applied=1 ok=0\n"
            "2026-06-01 12:00:01,000 INFO x: post_analysis evolution session_id=real applied=1 ok=1\n",
            encoding="utf-8",
        )
        total, removed = _filter_agent_log(log, dry_run=False)
        assert total == 2
        assert removed == 1
        text = log.read_text(encoding="utf-8")
        assert "iq07-sess" not in text
        assert "real" in text


def test_remove_test_skills():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "skills"
        (root / "unknown-tool").mkdir(parents=True)
        (root / "unknown-tool" / "SKILL.md").write_text("x", encoding="utf-8")
        removed = _remove_test_skills(root, dry_run=False)
        assert removed
        assert not (root / "unknown-tool").exists()
