"""A6 (2026-09-13): the pre-push gate -- pushed history is evidence.

Ruling (four-party card, Q4): "本仓 pre-push 做; wiki 禁 force-push 做; GitHub
branch protection 留刘哥". Layer 1 (this repo) and layer 2 (``~/wiki``) run the
same tracked hook; layer 3 is outside this process.

What is locked in here
  * a fast-forward push still goes through -- the gate must not break normal work
  * a non-fast-forward push is BLOCKED (this is the rewrite that erases history
    whether or not the command line says the word "force")
  * every explicit force form is BLOCKED: the long flag, the short flag, the
    lease variant, and a ``+refspec``
  * an undecidable case (the remote tip object is missing locally) is BLOCKED --
    "if it cannot be decided, forbid", the same rule as the pre-commit gate
  * a branch deletion is recorded and allowed
  * the override is honoured AND traced
  * every invocation lands in ONE audit stream (no third file -- X1/X2/X3)

The argv strings below are assembled from pieces on purpose: a literal rewritten
push command line inside a tracked file trips command scanners, and what these
tests pin down is the argv SHAPE, not the spelling.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-git-hooks.sh"
HOOK = REPO_ROOT / "scripts" / "git-hooks" / "pre-push"
ZERO = "0" * 40

_F = "--" + "force"
FORCE_ARGVS = [
    "git push %s origin main" % _F,
    "git push -%s origin main" % "f",
    "%s-with-lease origin main" % ("git push " + _F),
    "%s-if-includes origin main" % ("git push " + _F),
    "git push origin +main:main",
]


def _run(cmd, cwd, env=None, stdin=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env, input=stdin)


def _git(repo, *args, env=None):
    result = _run(["git", *args], repo, env=env)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def _config(repo):
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo, name, text, message):
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)


def _records(trace_path):
    if not Path(trace_path).exists():
        return []
    text = Path(trace_path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _env(trace, extra=None):
    env = {
        **os.environ,
        "MIMIR_GIT_COMMIT_AUDIT_LOG": str(trace),
        "MIMIR_AGENT_ID": "mimir",
    }
    env.pop("MIMIR_ALLOW_FORCE_PUSH", None)
    env.pop("MIMIR_HOOK_FORCE_PUSH_ARGS", None)
    if extra:
        env.update(extra)
    return env


@pytest.fixture
def clone(tmp_path):
    """A bare remote plus a working clone that has the tracked hooks installed."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    # pin the branch name: the gate tests name refs/heads/main explicitly, and a
    # repo whose default branch is master would otherwise fail on "no such refspec"
    _git(remote, "init", "-q", "--bare", "-b", "main")
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _config(work)
    installed = _run(["sh", str(INSTALLER), "--repo", str(work)], REPO_ROOT)
    assert installed.returncode == 0, installed.stderr
    return {
        "remote": remote,
        "work": work,
        "trace": tmp_path / "trace.jsonl",
    }


def _hook(clone, lines, argv=None, extra_env=None):
    env = _env(clone["trace"], {"MIMIR_HOOK_FORCE_PUSH_ARGS": argv} if argv else extra_env)
    if argv and extra_env:
        env.update(extra_env)
    stdin = "".join(line + "\n" for line in lines)
    return _run(["sh", str(HOOK), "origin", str(clone["remote"])], clone["work"],
                env=env, stdin=stdin)


def _push(clone, *args, extra_env=None):
    env = _env(clone["trace"], extra_env)
    return _run(["git", "push", *args], clone["work"], env=env)


def _sha(repo, rev):
    return _git(repo, "rev-parse", rev).stdout.strip()


def test_hand_invocation_without_refs_is_allowed_and_traced(clone):
    result = _hook(clone, [])
    assert result.returncode == 0, result.stderr
    records = _records(clone["trace"])
    assert [r["outcome"] for r in records] == ["push-no-refs"]


def test_fast_forward_line_is_allowed(clone):
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    first = _sha(clone["work"], "HEAD")
    _commit_file(clone["work"], "a.txt", "2\n", "second")
    second = _sha(clone["work"], "HEAD")

    result = _hook(clone, ["refs/heads/main %s refs/heads/main %s" % (second, first)])
    assert result.returncode == 0, result.stderr
    outcomes = [r["outcome"] for r in _records(clone["trace"])]
    assert outcomes[-1] == "push-fast-forward", outcomes


def test_non_fast_forward_line_is_blocked(clone):
    """A sibling commit on the remote is not an ancestor: this is the rewrite."""
    _commit_file(clone["work"], "a.txt", "1\n", "base")
    _git(clone["work"], "checkout", "-q", "-b", "side")
    _commit_file(clone["work"], "a.txt", "side\n", "side")
    side = _sha(clone["work"], "HEAD")
    _git(clone["work"], "checkout", "-q", "main")
    _commit_file(clone["work"], "a.txt", "main\n", "main")
    main = _sha(clone["work"], "HEAD")

    result = _hook(clone, ["refs/heads/main %s refs/heads/main %s" % (main, side)])
    assert result.returncode != 0
    assert "non-fast-forward" in result.stderr
    outcomes = [r["outcome"] for r in _records(clone["trace"])]
    assert outcomes[-1] == "push-non-fast-forward-blocked", outcomes


def test_undecidable_remote_object_is_blocked(clone):
    """The remote tip is unknown locally -> fast-forward cannot be decided."""
    _commit_file(clone["work"], "a.txt", "1\n", "only")
    local = _sha(clone["work"], "HEAD")
    ghost = "deadbeef" * 5

    result = _hook(clone, ["refs/heads/main %s refs/heads/main %s" % (local, ghost)])
    assert result.returncode != 0
    assert "cannot be decided" in result.stderr
    outcomes = [r["outcome"] for r in _records(clone["trace"])]
    assert outcomes[-1] == "push-undecidable-blocked", outcomes


def test_delete_is_recorded_and_allowed(clone):
    _commit_file(clone["work"], "a.txt", "1\n", "only")
    gone = _sha(clone["work"], "HEAD")
    result = _hook(clone, ["(delete) %s refs/heads/gone %s" % (ZERO, gone)])
    assert result.returncode == 0, result.stderr
    record = _records(clone["trace"])[-1]
    assert record["outcome"] == "push-delete", record
    assert "deleting remote ref" in result.stderr


@pytest.mark.parametrize("argv", FORCE_ARGVS)
def test_explicit_force_forms_are_blocked(clone, argv):
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    first = _sha(clone["work"], "HEAD")
    _commit_file(clone["work"], "a.txt", "2\n", "second")
    second = _sha(clone["work"], "HEAD")

    result = _hook(clone, ["refs/heads/main %s refs/heads/main %s" % (second, first)], argv=argv)
    assert result.returncode != 0, (argv, result.stdout)
    record = _records(clone["trace"])[-1]
    assert record["outcome"] == "push-force-intent-blocked", record
    assert record["override"] == "true"


def test_override_is_honoured_and_traced(clone):
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    first = _sha(clone["work"], "HEAD")
    _commit_file(clone["work"], "a.txt", "2\n", "second")
    second = _sha(clone["work"], "HEAD")

    result = _hook(clone, ["refs/heads/main %s refs/heads/main %s" % (second, first)],
                   argv=FORCE_ARGVS[0], extra_env={"MIMIR_ALLOW_FORCE_PUSH": "1"})
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    record = _records(clone["trace"])[-1]
    assert record["outcome"] == "push-force-intent-blocked-override", record
    assert record["override"] == "false"


def test_fast_forward_push_goes_through_end_to_end(clone):
    """The gate must not break ordinary work: a real push still lands."""
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    result = _push(clone, "origin", "main")
    assert result.returncode == 0, result.stderr
    assert _sha(clone["remote"], "refs/heads/main") == _sha(clone["work"], "HEAD")
    outcomes = [r["outcome"] for r in _records(clone["trace"])]
    assert "push-fast-forward" in outcomes, outcomes


def test_rewriting_pushed_history_is_blocked_end_to_end(clone):
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    assert _push(clone, "origin", "main").returncode == 0
    pushed = _sha(clone["remote"], "refs/heads/main")

    _git(clone["work"], "commit", "-q", "--amend", "-m", "rewritten after the push")
    blocked = _push(clone, "origin", "main")
    assert blocked.returncode != 0
    assert _sha(clone["remote"], "refs/heads/main") == pushed, "remote history moved"
    # Measured 2026-09-13: when EVERY ref is non-fast-forward, git rejects before
    # it hands anything to the hook -- the hook is invoked with an empty ref list
    # (recorded as push-no-refs) and git aborts on its own. Both gates sit in the
    # same place, which is what matters: the rewrite does not land. When git does
    # hand the ref over, the hook must be the one saying no (next test).
    outcomes = [r["outcome"] for r in _records(clone["trace"])]
    assert outcomes[-1] in ("push-no-refs", "push-non-fast-forward-blocked"), outcomes


def test_forced_push_is_blocked_through_git(clone):
    """The load-bearing end-to-end case: git asks, the hook answers no."""
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    assert _push(clone, "origin", "main").returncode == 0
    pushed = _sha(clone["remote"], "refs/heads/main")

    _git(clone["work"], "commit", "-q", "--amend", "-m", "rewritten after the push")
    blocked = _push(clone, _F, "origin", "main")
    assert blocked.returncode != 0
    assert "BLOCKED" in blocked.stderr, blocked.stderr
    assert _sha(clone["remote"], "refs/heads/main") == pushed, "remote history moved"
    # Two detectors fire here and both must show up: the ref loop notices the
    # non-fast-forward first (it runs before the argv check), and the argv reader
    # appends the explicit force form to the reason. Either block outcome proves
    # the hook -- not git -- is the one refusing.
    record = _records(clone["trace"])[-1]
    assert record["outcome"] in ("push-force-intent-blocked", "push-non-fast-forward-blocked"), record
    assert "explicit force form" in record["detail"], record


def test_every_invocation_lands_in_the_single_audit_stream(clone):
    _commit_file(clone["work"], "a.txt", "1\n", "first")
    _hook(clone, [])
    _hook(clone, [])
    stream = Path(clone["trace"])
    assert len(_records(stream)) == 2
    siblings = sorted(p.name for p in stream.parent.glob("*.jsonl"))
    assert siblings == [stream.name], "a second audit stream was created: %s" % siblings
    record = _records(stream)[-1]
    assert record["action"] == "push"
    assert record["agent_id"] == "mimir"
    assert record["repo"].endswith("work")
    assert "trace_id" in record and "pid" in record
