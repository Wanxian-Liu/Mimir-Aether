"""Tests for agent/run_context.py (Q3-B / A2+G-4 provenance).

Covers: trigger-source resolution precedence, git command classification,
run context lifecycle (incl. thread fallback), and the git audit trail file.
"""
import json
import os
import threading

import pytest

from agent import run_context


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("MIMIR_TRIGGER_SOURCE", raising=False)
    monkeypatch.delenv("MIMIR_AGENT_ID", raising=False)
    run_context.end_run()


# --- trigger source ---------------------------------------------------------

def test_explicit_wins_over_everything(monkeypatch):
    monkeypatch.setenv("MIMIR_TRIGGER_SOURCE", "env-source")
    assert run_context.resolve_trigger_source(
        explicit="explicit", platform="feishu", text="【自动唤醒】") == "explicit"


def test_env_wins_over_marker_and_platform(monkeypatch):
    monkeypatch.setenv("MIMIR_TRIGGER_SOURCE", "cron")
    assert run_context.resolve_trigger_source(
        platform="feishu", text="【自动唤醒】Buzz收件箱有 2 条新消息") == "cron"


def test_buzz_watcher_marker_beats_platform():
    """The whole point of A2: the buzz watcher wakes through Feishu, so the
    platform alone would report 'feishu' and hide the real trigger."""
    got = run_context.resolve_trigger_source(
        platform="feishu", text="【自动唤醒】Buzz收件箱有 1 条新消息(第 97 到 97 行)")
    assert got == "buzz-watcher"


def test_watchdog_marker():
    assert run_context.resolve_trigger_source(text="discussion-watchdog: card ready") == "watchdog"


def test_platform_mapping():
    assert run_context.resolve_trigger_source(platform="feishu") == "feishu"
    assert run_context.resolve_trigger_source(platform="local") == "cli"
    assert run_context.resolve_trigger_source(platform="api") == "api"
    assert run_context.resolve_trigger_source(platform="unknown-platform") == "unknown-platform"


def test_unknown_when_nothing_is_known():
    assert run_context.resolve_trigger_source() == "unknown"


# --- git command classification --------------------------------------------

@pytest.mark.parametrize("command,expected", [
    ("git commit -m 'x'", "commit"),
    ("cd ~/src/MimirAether && git commit -m 'x'", "commit"),
    ("git commit --amend --no-edit", "amend"),
    ("git commit -q --amend -m 'x'", "amend"),
    ("git push origin main", "push"),
    ("git rebase -i HEAD~2", "rebase"),
    ("git reset --hard HEAD~1", "reset"),
    ("git log --oneline -3", "read"),
    ("git status --short", "read"),
    ("echo hello > /tmp/x", None),
    ("pytest tests/agent -q", None),
    ("", None),
    (None, None),
])
def test_classify_git_command(command, expected):
    assert run_context.classify_git_command(command) == expected


def test_git_in_argument_position_is_not_an_invocation():
    """'echo git commit' mentions git but never runs it -- auditing it would
    pollute the trail with false positives."""
    assert run_context.classify_git_command("echo 'git commit -m x'") is None
    assert run_context.classify_git_command("grep -rn 'git commit' docs/") is None


def test_git_after_chain_operator_is_detected():
    assert run_context.classify_git_command("pytest -q; git push") == "push"
    assert run_context.classify_git_command("true && git commit --amend --no-edit") == "amend"


# --- run context lifecycle --------------------------------------------------

def test_begin_run_logs_and_returns_context(caplog):
    with caplog.at_level("INFO"):
        ctx = run_context.begin_run(trace_id="tr_test", trigger_source="feishu",
                                    platform="feishu", session_key="sess-1")
    assert ctx["trace_id"] == "tr_test"
    assert ctx["trigger_source"] == "feishu"
    assert ctx["agent_id"] == "mimir"
    assert ctx["session_key"] == "sess-1"
    assert run_context.current_run()["trace_id"] == "tr_test"
    assert any("[RUN]" in r.getMessage() for r in caplog.records)


def test_begin_run_accepts_metadata_source():
    """The buzz watcher posts metadata={'source': 'buzz-inbox-watcher'}."""
    ctx = run_context.begin_run(trace_id="tr_m", metadata={"source": "buzz-inbox-watcher"})
    assert ctx["trigger_source"] == "buzz-watcher"


def test_trace_id_is_minted_when_absent():
    ctx = run_context.begin_run(trigger_source="feishu")
    assert ctx["trace_id"].startswith("tr_")
    assert len(ctx["trace_id"]) > 6


def test_end_run_clears_context():
    run_context.begin_run(trace_id="tr_x")
    assert run_context.current_run()
    run_context.end_run()
    assert run_context.current_run() == {}


def test_agent_id_env_override(monkeypatch):
    monkeypatch.setenv("MIMIR_AGENT_ID", "mimir-canary")
    assert run_context.agent_id() == "mimir-canary"
    assert run_context.begin_run()["agent_id"] == "mimir-canary"


def test_thread_local_context_wins_over_fallback():
    """Tool calls may run on a worker thread: that thread's own context must
    win, and a thread without one falls back to the latest global run."""
    run_context.begin_run(trace_id="tr_main", trigger_source="feishu")
    seen = {}

    def worker():
        seen["before"] = run_context.current_run()
        run_context.begin_run(trace_id="tr_worker", trigger_source="api")
        seen["after"] = run_context.current_run()

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert seen["before"]["trace_id"] == "tr_main"  # process-wide fallback
    assert seen["after"]["trace_id"] == "tr_worker"  # thread-local wins
    assert run_context.current_run()["trace_id"] == "tr_main"  # main thread untouched


# --- git audit trail --------------------------------------------------------

def test_audit_writes_jsonl_with_provenance(tmp_path, monkeypatch):
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    run_context.begin_run(trace_id="tr_a", trigger_source="buzz-watcher",
                          session_key="sess-a")

    rec = run_context.audit_git_tool_call(
        "terminal", {"command": "cd ~/src/MimirAether && git commit -m 'x'"})

    assert rec is not None
    assert rec["class"] == "commit"
    assert rec["trace_id"] == "tr_a"
    assert rec["trigger_source"] == "buzz-watcher"
    assert rec["agent_id"] == "mimir"
    lines = [json.loads(l) for l in audit.read_text().splitlines()]
    assert len(lines) == 1
    assert lines[0]["class"] == "commit"
    assert lines[0]["trace_id"] == "tr_a"


def test_audit_ignores_non_git_and_git_reads(tmp_path, monkeypatch):
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    assert run_context.audit_git_tool_call("terminal", {"command": "ls -la"}) is None
    assert run_context.audit_git_tool_call("terminal", {"command": "git status"}) is None
    assert run_context.audit_git_tool_call("read_file", {"path": "x.py"}) is None
    assert not audit.exists()


def test_audit_reads_execute_code_arguments(tmp_path, monkeypatch):
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    run_context.begin_run(trace_id="tr_code")
    rec = run_context.audit_git_tool_call("execute_code", {"code": "subprocess.run(['git','push'])"})
    assert rec is not None
    assert rec["class"] == "push"


def test_audit_never_raises_on_unwritable_path(monkeypatch):
    """Provenance must not be able to break a tool call."""
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", "/proc/definitely/not/writable.jsonl")
    run_context.begin_run(trace_id="tr_bad")
    rec = run_context.audit_git_tool_call("terminal", {"command": "git commit -m x"})
    assert rec is not None  # returned even though the file write failed


def test_audit_repo_hint_from_cd(tmp_path, monkeypatch):
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    rec = run_context.audit_git_tool_call(
        "terminal", {"command": "cd /home/user/src/X && git push"})
    assert rec["repo"] == "/home/user/src/X"


def test_default_audit_path_uses_mimir_home(monkeypatch):
    monkeypatch.delenv("MIMIR_GIT_AUDIT_LOG", raising=False)
    monkeypatch.setenv("MIMIR_AETHER_HOME", "/home/user/.mimiraether")
    path = run_context._audit_log_path()
    assert path == os.path.join("/home/user/.mimiraether", "logs", "git-audit.jsonl")

def test_trigger_source_aliases_normalise():
    """One source must have ONE name in the trail (the watcher posts
    'buzz-inbox-watcher', markers produce 'buzz-watcher')."""
    assert run_context.resolve_trigger_source(explicit="buzz-inbox-watcher") == "buzz-watcher"
    assert run_context.resolve_trigger_source(explicit="self_restart") == "self-restart"
    assert run_context.resolve_trigger_source(explicit="cron") == "cron"


def test_begin_run_accepts_metadata_source_alias():
    ctx = run_context.begin_run(metadata={"trigger_source": "self_restart"})
    assert ctx["trigger_source"] == "self-restart"
