"""X1-c / X2-a acceptance tests (卡 `2026-09-12-四方讨论-审计流三处缺口-Q3后续.md`).

* **X1-c** — one audit record carries the whole class *set* of a chained command
  (before: first-invocation-only → commit-level coverage 0%).
* **X2-a** — run provenance travels into a CHILD process, so the commit hook
  (which runs outside this process) stamps a non-empty ``trace_id`` and the two
  audit streams finally share a join key.

The last test is the executable form of the Q3-1 replay: a real git repo, the
real tracked hook, a real shell spawn inside a run context — it answers
"which run produced which commit" without millisecond extrapolation.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent import run_context
from tools.environments.local import (
    LocalEnvironment,
    _make_run_env,
    _sanitize_subprocess_env,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SRC = REPO_ROOT / "scripts" / "git-hooks" / "pre-commit"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in ("MIMIR_TRIGGER_SOURCE", "MIMIR_AGENT_ID", "MIMIR_TRACE_ID"):
        monkeypatch.delenv(key, raising=False)
    run_context.end_run()
    yield
    run_context.end_run()


# --- X1-c: the class set ----------------------------------------------------

@pytest.mark.parametrize("command,expected", [
    # the real agent chain that produced 0% commit coverage before X1-c
    ("cd ~/wiki && cp a b && git add card.md && git commit -m 'x' && git push",
     ["add", "commit", "push"]),
    ("git add -A && git commit --amend --no-edit", ["add", "amend"]),
    ("git commit -m x && git commit --amend -m y", ["commit", "amend"]),
    ("git log --oneline && git commit -m x", ["commit"]),   # reads are dropped
    ("git status --short && git log -1", []),
    ("ls -la", []),
    ("", []),
    (None, []),
    ("echo 'git commit -m x'", []),                         # argument, not a call
    ("subprocess.run(['git', 'push'])", ["push"]),
])
def test_class_set(command, expected):
    assert run_context.classify_git_command_classes(command) == expected


def test_first_class_api_is_unchanged():
    """The legacy single-value API keeps its old semantics (first invocation)."""
    chain = "git add a && git commit -m x && git push"
    assert run_context.classify_git_command(chain) == "add"
    assert run_context.classify_git_command_classes(chain) == ["add", "commit", "push"]


def test_audit_record_carries_class_set(tmp_path, monkeypatch):
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    run_context.begin_run(trace_id="tr_chain")

    command = "cd /home/user/src/X && git add a && git commit -m x && git push"
    rec = run_context.audit_git_tool_call("terminal", {"command": command})

    assert rec["classes"] == ["add", "commit", "push"]
    assert rec["class"] == "add"            # legacy field == first class
    assert rec["command_len"] == len(command)
    written = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    assert written["classes"] == ["add", "commit", "push"]


def test_command_len_exposes_truncation(tmp_path, monkeypatch):
    """A truncated `command` must not silently hide what the audit saw."""
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    rec = run_context.audit_git_tool_call(
        "terminal", {"command": "git commit -m " + "x" * 600})
    assert rec["classes"] == ["commit"]
    assert len(rec["command"]) == 400
    assert rec["command_len"] > 400


def test_repo_spellings_normalise_to_one_join_key(tmp_path, monkeypatch):
    """``~/wiki`` and ``/home/<user>/wiki`` must be the SAME join key (X1 note)."""
    audit = tmp_path / "git-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(audit))
    home = os.path.expanduser("~")
    rec_tilde = run_context.audit_git_tool_call(
        "terminal", {"command": "cd ~/wiki && git push"})
    rec_abs = run_context.audit_git_tool_call(
        "terminal", {"command": f"cd {home}/wiki && git push"})
    assert rec_tilde["repo"] == rec_abs["repo"] == os.path.realpath(home + "/wiki")
    assert "~" not in rec_tilde["repo"]


# --- X2-a: provenance reaches the child -------------------------------------

def test_foreground_env_carries_provenance():
    run_context.begin_run(trace_id="tr_env", trigger_source="api")
    env = _make_run_env({})
    assert env["MIMIR_TRACE_ID"] == "tr_env"
    assert env["MIMIR_AGENT_ID"] == "mimir"


def test_background_env_carries_provenance():
    run_context.begin_run(trace_id="tr_bg")
    assert _sanitize_subprocess_env({}, {})["MIMIR_TRACE_ID"] == "tr_bg"


def test_no_run_no_provenance_keys():
    assert run_context.child_env_injection() == {}
    env = _make_run_env({})
    assert "MIMIR_TRACE_ID" not in env


def test_apply_child_env_does_not_mutate_input():
    run_context.begin_run(trace_id="tr_apply")
    base = {"A": "1"}
    out = run_context.apply_child_env(base)
    assert out["A"] == "1"
    assert out["MIMIR_TRACE_ID"] == "tr_apply"
    assert "MIMIR_TRACE_ID" not in base


def test_agent_id_injection_honours_env_override(monkeypatch):
    monkeypatch.setenv("MIMIR_AGENT_ID", "mimir-canary")
    run_context.begin_run(trace_id="tr_canary")
    assert run_context.child_env_injection()["MIMIR_AGENT_ID"] == "mimir-canary"


def test_provenance_keys_are_exact_not_wildcard():
    """Security review (X2-a): the injected key set is closed, not MIMIR_*."""
    run_context.begin_run(trace_id="tr_keys")
    injected = run_context.child_env_injection()
    assert set(injected) == set(run_context.PROVENANCE_ENV_KEYS)


# --- Q3-1 replay: which run produced which commit ---------------------------

def _init_repo(path: Path) -> None:
    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)

    _git("init", "-q")
    _git("config", "user.name", "Mimir")
    _git("config", "user.email", "mimir@mimiraether.local")
    _git("config", "commit.gpgsign", "false")
    hook_dir = path / ".git" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HOOK_SRC, hook_dir / "pre-commit")
    (hook_dir / "pre-commit").chmod(0o755)


@pytest.mark.skipif(not HOOK_SRC.exists(), reason="tracked git hook missing")
def test_commit_hook_stamps_trace_id_end_to_end(tmp_path, monkeypatch):
    """The two streams must join on trace_id for one real commit."""
    commit_audit = tmp_path / "git-commit-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_COMMIT_AUDIT_LOG", str(commit_audit))
    monkeypatch.setenv("MIMIR_GIT_AUDIT_LOG", str(tmp_path / "git-audit.jsonl"))

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "card.md").write_text("evidence\n", encoding="utf-8")

    run_context.begin_run(trace_id="tr_replay", trigger_source="api",
                          session_key="sess-replay")
    command = f"cd {repo} && git add card.md && git commit -m replay"

    # A stream (tool level) for the very same command: classes must include commit
    rec = run_context.audit_git_tool_call("terminal", {"command": command})
    assert rec["classes"] == ["add", "commit"]
    assert rec["trace_id"] == "tr_replay"

    # real shell spawn through the same env builder the terminal tool uses
    result = LocalEnvironment(cwd=str(repo)).execute(command, timeout=60)
    assert result["returncode"] == 0, result["output"]

    lines = [json.loads(line) for line in
             commit_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "commit hook wrote no audit line"
    hook_rec = lines[-1]
    assert hook_rec["action"] == "commit"
    # X2-a: no longer structurally empty
    assert hook_rec["trace_id"] == "tr_replay", hook_rec
    # X1 note + X2-a: the same normalised repo key on both sides
    assert os.path.realpath(hook_rec["repo"]) == os.path.realpath(rec["repo"])


@pytest.mark.skipif(not HOOK_SRC.exists(), reason="tracked git hook missing")
def test_hook_trace_id_is_empty_without_a_run(tmp_path, monkeypatch):
    """Control case: the injection - not the ambient env - is what fills it."""
    commit_audit = tmp_path / "git-commit-audit.jsonl"
    monkeypatch.setenv("MIMIR_GIT_COMMIT_AUDIT_LOG", str(commit_audit))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "card.md").write_text("evidence\n", encoding="utf-8")

    result = LocalEnvironment(cwd=str(repo)).execute(
        f"cd {repo} && git add card.md && git commit -m noreplay", timeout=60)
    assert result["returncode"] == 0, result["output"]

    lines = [json.loads(line) for line in
             commit_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert lines[-1]["trace_id"] == ""
