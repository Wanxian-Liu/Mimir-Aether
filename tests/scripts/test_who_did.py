"""A5 (2026-09-13): the attribution self-check entry (ф2).

Ruling (Hermes receipt, Q3): ф2 adopted, three entry points (commit / file /
card), and "不可判" is the soul of the design -- the X2-c rule that a time
approximation must never masquerade as an attribution.

These tests pin the two-independent-things contract:
  declaration  = what someone wrote down (commit trailer / card author)
  corroboration = what the machine recorded (hook stream joined exactly by
                  repo + head == the commit parent; tool stream as a fallback)
and the verdicts: consistent / mismatch / undetermined, with the undetermined
cases named explicitly (missing side, ambiguous evidence, pre-boundary history).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "who_did.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import who_did  # noqa: E402  (the module under test)


def _run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)


def _git(repo, *args, env=None):
    result = _run(["git", *args], repo, env=env)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def _config(repo):
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit(repo, message, name="a.txt", text=None, env=None):
    # unique content per call: re-writing identical bytes gives git nothing to
    # commit ("nothing to commit, working tree clean"), which silently turns a
    # fixture into a no-op and fails the NEXT assertion instead of this one.
    (repo / name).write_text(text if text is not None else message + "\n", encoding="utf-8")
    _git(repo, "add", name)
    merged = {**os.environ}
    if env:
        merged.update(env)
    _git(repo, "commit", "-q", "-m", message, env=merged)
    return _sha(repo, "HEAD")


def _sha(repo, rev):
    return _git(repo, "rev-parse", rev).stdout.strip()


def _real(repo):
    return os.path.realpath(str(repo))


def _hook_record(repo, head, agent="mimir", trace="run_a", action="commit"):
    return {
        "ts": "2026-09-13T00:00:00Z",
        "agent_id": agent,
        "trace_id": trace,
        "action": action,
        "outcome": "commit",
        "override": "false",
        "repo": _real(repo),
        "branch": "main",
        "head": head,
        "committer": "Mimir <mimir@mimiraether.local>",
        "head_author": "Mimir <mimir@mimiraether.local>",
        "staged_files": 1,
        "pid": 1,
    }


def _tool_record(repo, ts, agent="mimir", trace="run_a", classes=None):
    return {
        "ts": float(ts),
        "tool": "terminal",
        "class": (classes or ["add", "commit"])[0],
        "classes": classes or ["add", "commit"],
        "repo": _real(repo),
        "trace_id": trace,
        "trigger_source": "buzz-watcher",
        "agent_id": agent,
        "session_key": trace,
        "pid": 1,
        "command_len": 10,
    }


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _config(path)
    return path


def _verdict(repo, rev, hooks=(), tools=()):
    result = who_did.check_commit(str(repo), rev, list(hooks), list(tools))
    assert "error" not in result, result
    return result


def _commit_ts(repo, rev="HEAD"):
    return int(_git(repo, "log", "-1", "--format=%ct", rev).stdout.strip())


def test_declaration_and_evidence_agree(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: mimir")
    result = _verdict(repo, sha, hooks=[_hook_record(repo, parent)])
    verdict = result["verdict"]
    assert verdict["verdict"] == who_did.CONSISTENT
    assert verdict["declared_ids"] == ["mimir"]
    assert verdict["corroborated_ids"] == ["mimir"]
    assert result["corroboration"]["authoritative"] == "hook"


def test_declaration_disagreeing_with_evidence_is_a_mismatch(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: hermes")
    verdict = _verdict(repo, sha, hooks=[_hook_record(repo, parent, agent="mimir")])["verdict"]
    assert verdict["verdict"] == who_did.MISMATCH
    assert verdict["declared_ids"] == ["hermes"]
    assert verdict["corroborated_ids"] == ["mimir"]


def test_declaration_without_corroboration_is_undetermined(repo):
    sha = _commit(repo, "sole commit\n\nAgent: mimir")
    result = _verdict(repo, sha)
    verdict = result["verdict"]
    assert verdict["verdict"] == who_did.UNDETERMINED
    assert verdict["boundary"] is False
    assert any("corroboration missing" in r for r in verdict["reasons"]), verdict["reasons"]


def test_pre_boundary_history_is_undetermined_not_attributed(repo):
    old = {"GIT_AUTHOR_DATE": "2026-08-01T00:00:00+00:00",
           "GIT_COMMITTER_DATE": "2026-08-01T00:00:00+00:00"}
    # even WITH a trailer the answer stays "不可判": before the boundary the git
    # signature is not evidence (section 8), and there is no machine record either
    sha = _commit(repo, "august commit\n\nAgent: mimir", env=old)
    verdict = _verdict(repo, sha)["verdict"]
    assert verdict["verdict"] == who_did.UNDETERMINED
    assert verdict["boundary"] is True
    assert any("section 8" in r for r in verdict["reasons"]), verdict["reasons"]


def test_two_runs_sharing_a_parent_is_ambiguous(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: mimir")
    hooks = [
        _hook_record(repo, parent, trace="run_one"),
        _hook_record(repo, parent, trace="run_two"),
    ]
    result = _verdict(repo, sha, hooks=hooks)
    assert result["corroboration"]["ambiguous"] is True
    assert result["verdict"]["verdict"] == who_did.UNDETERMINED
    assert any("more than one run" in n for n in result["corroboration"]["notes"])


def test_empty_trace_id_is_undecidable(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: mimir")
    result = _verdict(repo, sha, hooks=[_hook_record(repo, parent, trace="")])
    assert result["verdict"]["verdict"] == who_did.UNDETERMINED
    assert any("EMPTY trace_id" in n for n in result["corroboration"]["notes"])


def test_tool_stream_is_the_fallback_when_the_hook_stream_is_silent(repo):
    sha = _commit(repo, "sole commit\n\nAgent: mimir")
    tools = [_tool_record(repo, _commit_ts(repo, sha) - 30)]
    result = _verdict(repo, sha, tools=tools)
    assert result["corroboration"]["authoritative"] == "tool"
    assert result["verdict"]["verdict"] == who_did.CONSISTENT


def test_ambiguous_tool_window_is_never_used_as_evidence(repo):
    sha = _commit(repo, "sole commit\n\nAgent: mimir")
    ts = _commit_ts(repo, sha)
    tools = [
        _tool_record(repo, ts - 30, trace="run_one"),
        _tool_record(repo, ts - 20, trace="run_two"),
    ]
    result = _verdict(repo, sha, tools=tools)
    assert result["corroboration"]["ambiguous"] is True
    assert result["verdict"]["verdict"] == who_did.UNDETERMINED
    assert any("time approximation" in n for n in result["corroboration"]["notes"])


def test_out_of_set_id_is_flagged_but_not_rejected(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: bob")
    verdict = _verdict(repo, sha, hooks=[_hook_record(repo, parent, agent="bob")])["verdict"]
    assert verdict["verdict"] == who_did.CONSISTENT
    assert verdict["flagged_ids"] == ["bob"]
    assert set(who_did.ALLOWED_IDS) == {"mimir", "hermes", "openclaw", "loki"}


CARD_TEXT = """---
author: {author}
title: fixture card
---

# fixture

Body text, deliberately short.
"""


def _write_card(repo, name, author):
    cards = repo / "cards"
    cards.mkdir(exist_ok=True)
    path = cards / name
    path.write_text(CARD_TEXT.format(author=author), encoding="utf-8")
    return path


def test_card_entry_reads_frontmatter_and_agrees_with_the_commit(repo):
    card = _write_card(repo, "card.md", "mimir")
    _commit(repo, "base")
    parent = _sha(repo, "HEAD")
    _git(repo, "add", "cards/card.md")
    _git(repo, "commit", "-q", "-m", "card\n\nAgent: mimir")
    sha = _sha(repo, "HEAD")

    result = who_did.check_card(str(repo), str(card), [_hook_record(repo, parent)], [])
    assert result["entry"] == "card"
    assert result["card_status"] == "ok"
    assert result["verdict"]["verdict"] == who_did.CONSISTENT
    assert result["verdict"]["declared_ids"] == ["mimir"]
    assert sha == result["target"]


def test_card_author_disagreeing_with_the_commit_is_a_mismatch(repo):
    card = _write_card(repo, "card2.md", "hermes")
    _commit(repo, "base")
    parent = _sha(repo, "HEAD")
    _git(repo, "add", "cards/card2.md")
    _git(repo, "commit", "-q", "-m", "card\n\nAgent: mimir")
    result = who_did.check_card(str(repo), str(card), [_hook_record(repo, parent)], [])
    assert result["verdict"]["verdict"] == who_did.MISMATCH
    assert set(result["verdict"]["declared_ids"]) == {"hermes", "mimir"}


def test_file_entry_uses_the_commit_that_touched_it(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: mimir", name="b.txt", text="b\n")
    result = who_did.check_file(str(repo), "b.txt", [_hook_record(repo, parent)], [])
    assert result["entry"] == "file"
    assert result["target"] == sha
    assert result["verdict"]["verdict"] == who_did.CONSISTENT


def test_untracked_file_has_nothing_to_attribute(repo):
    (repo / "draft.txt").write_text("draft\n", encoding="utf-8")
    result = who_did.check_file(str(repo), "draft.txt", [], [])
    assert result["verdict"]["verdict"] == who_did.UNDETERMINED
    assert result["target"] is None
    assert any("no commit history" in r for r in result["verdict"]["reasons"])


def test_missing_path_is_an_error_not_a_verdict(repo):
    result = who_did.check_file(str(repo), "nope.txt", [], [])
    assert "error" in result


def _cli(repo, args, hook_records, tool_records):
    streams = repo.parent / (repo.name + "-streams")
    streams.mkdir(exist_ok=True)
    hook_path = streams / "hook.jsonl"
    tool_path = streams / "tool.jsonl"
    hook_path.write_text("".join(json.dumps(r) + "\n" for r in hook_records), encoding="utf-8")
    tool_path.write_text("".join(json.dumps(r) + "\n" for r in tool_records), encoding="utf-8")
    env = {
        **os.environ,
        "MIMIR_GIT_COMMIT_AUDIT_LOG": str(hook_path),
        "MIMIR_GIT_AUDIT_LOG": str(tool_path),
    }
    return _run([sys.executable, str(SCRIPT), *args], repo, env=env)


def test_cli_exit_codes_are_the_verdict(repo):
    _commit(repo, "first")
    parent = _sha(repo, "HEAD")
    sha = _commit(repo, "second\n\nAgent: mimir")

    ok = _cli(repo, ["--commit", sha, "--quiet"], [_hook_record(repo, parent)], [])
    assert ok.returncode == who_did.EXIT_CONSISTENT, ok.stdout + ok.stderr
    assert ok.stdout.startswith("consistent:")

    unknown = _cli(repo, ["--commit", sha, "--quiet"], [], [])
    assert unknown.returncode == who_did.EXIT_UNDETERMINED, unknown.stdout
    assert "undetermined" in unknown.stdout

    other = tmp = None
    _commit(repo, "third\n\nAgent: loki")
    mismatch = _cli(repo, ["--commit", "HEAD", "--quiet"], [_hook_record(repo, sha)], [])
    assert mismatch.returncode == who_did.EXIT_MISMATCH, mismatch.stdout


def test_cli_auto_detects_card_and_file_modes(repo):
    card = _write_card(repo, "card3.md", "mimir")
    _commit(repo, "base")
    parent = _sha(repo, "HEAD")
    _git(repo, "add", "cards/card3.md")
    _git(repo, "commit", "-q", "-m", "card\n\nAgent: mimir")
    hook = _hook_record(repo, parent)

    as_card = _cli(repo, [str(card), "--json"], [hook], [])
    assert as_card.returncode == who_did.EXIT_CONSISTENT, as_card.stdout
    payload = json.loads(as_card.stdout)
    assert payload["entry"] == "card"
    assert payload["verdict"]["verdict"] == who_did.CONSISTENT
    assert payload["streams"]["hook"]["records"] == 1

    as_file = _cli(repo, ["a.txt", "--json"], [hook], [])
    assert json.loads(as_file.stdout)["entry"] == "file"

    bad = _cli(repo, ["--commit", "HEAD", "--file", "a.txt"], [hook], [])
    assert bad.returncode == who_did.EXIT_ERROR
