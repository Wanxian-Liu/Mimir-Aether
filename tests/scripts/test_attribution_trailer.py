"""A2 (2026-09-13): attribution trailer hook + non-blocking card checker.

Ruling from 刘哥: attribution marking becomes standard practice, and it must
NOT block anything. These tests lock in that contract:

* ``scripts/git-hooks/commit-msg`` always exits 0 -- a missing trailer is a
  warning plus a recorded outcome, never a rejected commit.
* an author-written trailer always wins over the environment value (a human
  statement beats a mechanism).
* every invocation appends exactly one line to the SAME audit stream the
  pre-commit hook uses (one stream, no third file -- the X1/X2/X3 lesson).
* ``scripts/check_card_author.py`` exits 0 even when cards are un-attributed.
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "git-hooks" / "commit-msg"
CHECKER = REPO_ROOT / "scripts" / "check_card_author.py"

ALLOWED_IDS = ("mimir", "hermes", "openclaw", "loki")


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location("check_card_author_under_test", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_hook(msg_path: Path, audit_log: Path, agent_id):
    env = dict(os.environ)
    env.pop("MIMIR_AGENT_ID", None)
    env["MIMIR_GIT_COMMIT_AUDIT_LOG"] = str(audit_log)
    if agent_id is not None:
        env["MIMIR_AGENT_ID"] = agent_id
    return subprocess.run(
        ["sh", str(HOOK), str(msg_path)], capture_output=True, text=True, env=env
    )


def _audit_lines(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# commit-msg hook                                                             #
# --------------------------------------------------------------------------- #
def test_appends_trailer_from_environment(tmp_path):
    msg = tmp_path / "MSG"
    msg.write_text("feat: something\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"

    result = _run_hook(msg, audit, "mimir")

    assert result.returncode == 0
    assert "Agent: mimir" in msg.read_text(encoding="utf-8")
    lines = _audit_lines(audit)
    assert len(lines) == 1
    assert lines[0]["action"] == "signature"
    assert lines[0]["signed_by"] == "auto"
    assert lines[0]["id_known"] == "known"
    assert lines[0]["agent_id"] == "mimir"


def test_message_untouched_and_never_blocked_without_environment(tmp_path):
    msg = tmp_path / "MSG"
    original = "feat: unsigned work\n"
    msg.write_text(original, encoding="utf-8")
    audit = tmp_path / "audit.jsonl"

    result = _run_hook(msg, audit, None)

    assert result.returncode == 0, "non-blocking ruling: never reject a commit"
    assert msg.read_text(encoding="utf-8") == original
    assert "unsigned" in result.stderr
    lines = _audit_lines(audit)
    assert len(lines) == 1
    assert lines[0]["signed_by"] == "none"
    assert lines[0]["agent_id"] == ""


def test_explicit_trailer_wins_over_environment(tmp_path):
    msg = tmp_path / "MSG"
    msg.write_text("feat: cross-authored\n\nAgent: loki\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"

    result = _run_hook(msg, audit, "mimir")

    assert result.returncode == 0
    text = msg.read_text(encoding="utf-8")
    assert text.count("Agent:") == 1, "an existing trailer must not be duplicated"
    assert "Agent: loki" in text
    assert _audit_lines(audit)[0]["signed_by"] == "explicit"
    assert _audit_lines(audit)[0]["agent_id"] == "loki"


def test_unknown_id_is_recorded_not_rejected(tmp_path):
    msg = tmp_path / "MSG"
    msg.write_text("feat: odd identity\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"

    result = _run_hook(msg, audit, "not-an-agent")

    assert result.returncode == 0, "an unknown id is a finding, not a failure"
    assert "not-an-agent" in msg.read_text(encoding="utf-8")
    line = _audit_lines(audit)[0]
    assert line["id_known"] == "unknown"
    assert line["outcome"] == "signed-auto-unknown-id"


def test_missing_message_file_exits_zero(tmp_path):
    audit = tmp_path / "audit.jsonl"
    result = _run_hook(tmp_path / "does-not-exist", audit, "mimir")
    assert result.returncode == 0
    assert _audit_lines(audit) == []


def test_agreed_id_set_is_honoured(tmp_path):
    """Every agreed id must be recognised; nothing else should be."""
    for agent_id in ALLOWED_IDS:
        msg = tmp_path / f"MSG-{agent_id}"
        msg.write_text("feat: x\n", encoding="utf-8")
        audit = tmp_path / f"audit-{agent_id}.jsonl"
        result = _run_hook(msg, audit, agent_id)
        assert result.returncode == 0
        assert _audit_lines(audit)[0]["id_known"] == "known"


# --------------------------------------------------------------------------- #
# card frontmatter checker                                                    #
# --------------------------------------------------------------------------- #
def _card(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_checker_classifies_canonical(tmp_path, checker):
    path = _card(tmp_path, "a.md", "---\ntitle: x\nauthor: mimir\n---\n\nbody\n")
    assert checker.classify(path)["status"] == "ok"


def test_checker_classifies_legacy_by_field(tmp_path, checker):
    path = _card(tmp_path, "b.md", "---\ntitle: x\nby: mimir\n---\n\nbody\n")
    result = checker.classify(path)
    assert result["status"] == "legacy"
    assert "by: mimir" in result["detail"]


def test_checker_classifies_capitalised_author_as_legacy(tmp_path, checker):
    path = _card(tmp_path, "c.md", "---\ntitle: x\nauthor: Mimir\n---\n\nbody\n")
    assert checker.classify(path)["status"] == "legacy"


def test_checker_flags_unknown_id(tmp_path, checker):
    path = _card(tmp_path, "d.md", "---\ntitle: x\nauthor: nobody\n---\n\nbody\n")
    assert checker.classify(path)["status"] == "unknown-id"


def test_checker_reports_missing_field(tmp_path, checker):
    path = _card(tmp_path, "e.md", "---\ntitle: x\n---\n\nbody\n")
    assert checker.classify(path)["status"] == "missing"


def test_checker_reports_absent_frontmatter(tmp_path, checker):
    path = _card(tmp_path, "f.md", "# no frontmatter here\n\nbody\n")
    assert checker.classify(path)["status"] == "no-frontmatter"


def test_checker_is_non_recursive_by_default(tmp_path, checker):
    _card(tmp_path, "top.md", "---\nauthor: mimir\n---\n")
    nested = tmp_path / "archive"
    nested.mkdir()
    _card(nested, "old.md", "---\ntitle: y\n---\n")

    assert len(checker.collect([str(tmp_path)])) == 1
    assert len(checker.collect([str(tmp_path)], recursive=True)) == 2


def test_checker_exit_code_is_zero_even_when_cards_lack_attribution(tmp_path, checker):
    _card(tmp_path, "g.md", "---\ntitle: z\n---\n\nno author field\n")
    assert checker.main([str(tmp_path), "--quiet"]) == 0
    assert checker.main([str(tmp_path), "--json"]) == 0
