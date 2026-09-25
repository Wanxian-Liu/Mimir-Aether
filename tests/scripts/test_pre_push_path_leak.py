"""R6 (2026-09-26): the pre-push published-path scan.

Why this gate exists
  An absolute home path in a pushed line publishes the operator's account name.
  The 2026-09-25/26 GitHub audit found the class three times (worktree files,
  migration snapshots, an unmerged local branch), each time by hand. A finding
  that no gate can re-check is a finding that comes back, so the rule becomes a
  push-time gate instead of a paragraph in a report.

What is locked in here
  * an added line carrying the home path is BLOCKED
  * the clean twin (same shape, path abstracted) still goes through -- without
    this arm the gate would be indistinguishable from "block everything"
  * scripts/migrations/ is exempt: those are frozen execution snapshots and
    editing them would falsify the audit trail
  * the override is honoured AND traced (the trace line is what makes it
    reviewable, not the prose in the header)
  * a NEW branch is scanned against its whole tree, so a leak that is carried
    in by an earlier commit is still caught after unrelated commits land on top
  * ordinary work is not broken: a clean push still lands, end to end

The literal name is never written down here either. The needle is derived from
``id -un`` at run time (with MIMIR_PATH_LEAK_NEEDLE as the test seam), because a
test that spells the leak out would itself be the leak.
"""
import getpass
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-git-hooks.sh"
HOOK = REPO_ROOT / "scripts" / "git-hooks" / "pre-push"
ZERO = "0" * 40

# Derived, never spelled out. /home/ is a literal prefix; the account name comes
# from the environment so this file stays clean under its own gate.
NEEDLE = "/home/" + getpass.getuser()


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
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)


def _records(trace_path):
    path = Path(trace_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _env(trace, extra=None):
    env = {
        **os.environ,
        "MIMIR_GIT_COMMIT_AUDIT_LOG": str(trace),
        "MIMIR_AGENT_ID": "mimir",
    }
    for key in ("MIMIR_ALLOW_FORCE_PUSH", "MIMIR_HOOK_FORCE_PUSH_ARGS",
                "MIMIR_ALLOW_PATH_LEAK", "MIMIR_PATH_LEAK_NEEDLE"):
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


@pytest.fixture
def clone(tmp_path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _config(work)
    installed = _run(["sh", str(INSTALLER), "--repo", str(work)], REPO_ROOT)
    assert installed.returncode == 0, installed.stderr
    _commit_file(work, "base.txt", "base\n", "base")
    return {"remote": remote, "work": work, "trace": tmp_path / "trace.jsonl"}


def _hook(clone, lines, extra_env=None):
    stdin = "".join(line + "\n" for line in lines)
    return _run(["sh", str(HOOK), "origin", str(clone["remote"])], clone["work"],
                env=_env(clone["trace"], extra_env), stdin=stdin)


def _ref(clone, ref, new, old):
    return "%s %s %s %s" % (ref, new, ref, old)


def _sha(repo, rev):
    return _git(repo, "rev-parse", rev).stdout.strip()


def test_added_home_path_is_blocked(clone):
    """Positive arm: the bad shape must not pass."""
    _commit_file(clone["work"], "leak.txt", "root=%s/src/thing\n" % NEEDLE, "leaked path")
    new, old = _sha(clone["work"], "HEAD"), _sha(clone["work"], "HEAD~1")

    result = _hook(clone, [_ref(clone, "refs/heads/main", new, old)])
    assert result.returncode != 0
    assert "BLOCKED" in result.stderr, result.stderr
    record = _records(clone["trace"])[-1]
    assert record["outcome"] == "push-path-leak-blocked", record
    assert record["override"] == "true", record


def test_clean_twin_still_passes(clone):
    """Negative arm: same shape, path abstracted -> the gate must not fire.

    Without this arm a gate that blocks everything would look identical.
    """
    _commit_file(clone["work"], "leak.txt", "root=%s/src/thing\n" % NEEDLE, "leaked path")
    leaked = _sha(clone["work"], "HEAD")
    _commit_file(clone["work"], "clean.txt", "root=$HOME/src/thing\n", "abstracted path")
    new = _sha(clone["work"], "HEAD")

    result = _hook(clone, [_ref(clone, "refs/heads/main", new, leaked)])
    assert result.returncode == 0, result.stderr
    assert _records(clone["trace"])[-1]["outcome"] == "push-fast-forward"


def test_frozen_migration_snapshots_are_exempt(clone):
    """scripts/migrations/ holds execution snapshots; editing them would rewrite
    the audit trail. The gate must not force that."""
    _commit_file(clone["work"], "scripts/migrations/snap.txt", "frozen=%s/old\n" % NEEDLE, "snapshot")
    new, old = _sha(clone["work"], "HEAD"), _sha(clone["work"], "HEAD~1")

    result = _hook(clone, [_ref(clone, "refs/heads/main", new, old)])
    assert result.returncode == 0, result.stderr
    assert _records(clone["trace"])[-1]["outcome"] == "push-fast-forward"


def test_override_is_honoured_and_traced(clone):
    _commit_file(clone["work"], "leak.txt", "a=%s/x\n" % NEEDLE, "leaked path")
    new, old = _sha(clone["work"], "HEAD"), _sha(clone["work"], "HEAD~1")

    result = _hook(clone, [_ref(clone, "refs/heads/main", new, old)],
                   extra_env={"MIMIR_ALLOW_PATH_LEAK": "1"})
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    record = _records(clone["trace"])[-1]
    assert record["outcome"] == "push-path-leak-blocked-override", record
    assert record["override"] == "false", record


def test_new_branch_tree_is_scanned_not_just_the_tip(clone):
    """A new branch has no remote predecessor to diff against, so the whole tree
    is scanned. A leak carried in earlier must survive unrelated later commits."""
    _git(clone["work"], "checkout", "-q", "-b", "carrier")
    _commit_file(clone["work"], "carried.txt", "carry=%s/z\n" % NEEDLE, "carry the path")
    _commit_file(clone["work"], "later.txt", "unrelated\n", "unrelated")
    tip = _sha(clone["work"], "HEAD")

    result = _hook(clone, [_ref(clone, "refs/heads/carrier", tip, ZERO)])
    assert result.returncode != 0, result.stderr
    assert _records(clone["trace"])[-1]["outcome"] == "push-path-leak-blocked"


def test_clean_push_still_lands_end_to_end(clone):
    _commit_file(clone["work"], "ok.txt", "fine\n", "clean")
    result = _run(["git", "push", "-q", "origin", "main"], clone["work"], env=_env(clone["trace"]))
    assert result.returncode == 0, result.stderr
    assert _sha(clone["remote"], "refs/heads/main") == _sha(clone["work"], "HEAD")


def test_leaking_push_is_refused_end_to_end(clone):
    """The load-bearing case: git asks, the hook answers no, the remote is unmoved."""
    _git(clone["work"], "checkout", "-q", "-b", "leaky")
    _commit_file(clone["work"], "leak.txt", "q=%s/w\n" % NEEDLE, "leaked path")

    result = _run(["git", "push", "-q", "origin", "leaky"], clone["work"], env=_env(clone["trace"]))
    assert result.returncode != 0
    assert _run(["git", "rev-parse", "--verify", "refs/heads/leaky"],
                clone["remote"]).returncode != 0, "the remote branch exists anyway"


def test_stale_fork_point_does_not_hide_the_leak(clone):
    """The failure this gate was caught on (2026-09-26).

    A new branch forked long ago carries files that main has since cleaned up.
    Against the merge-base the diff is EMPTY -- the branch adds nothing -- so a
    diff-based scan sees nothing while the whole tree is about to be published.
    Measured on the real repo: 526 hits, 813 commits behind, invisible.

    Construction: leak -> clean up on main -> push main -> branch off the leak
    commit. merge-base(branch, origin/main) == the leak commit, so the diff
    range is empty on purpose. Only a whole-tree scan can answer.
    """
    _commit_file(clone["work"], "leaked.txt", "v=%s/stale\n" % NEEDLE, "leak")
    leak = _sha(clone["work"], "HEAD")
    _git(clone["work"], "rm", "-q", "leaked.txt")
    _git(clone["work"], "commit", "-q", "-m", "clean up the path")
    pushed = _run(["git", "push", "-q", "origin", "main"], clone["work"], env=_env(clone["trace"]))
    assert pushed.returncode == 0, pushed.stderr

    # Sanity: the diff range really is empty, so the arm cannot pass by accident.
    diff = _git(clone["work"], "diff", "--name-only", leak, leak).stdout.strip()
    assert diff == "", diff

    result = _hook(clone, [_ref(clone, "refs/heads/stale", leak, ZERO)])
    assert result.returncode != 0, "the stale branch slipped through"
    record = _records(clone["trace"])[-1]
    assert record["outcome"] == "push-path-leak-blocked", record


def test_hook_source_does_not_spell_the_name_out(clone):
    """The gate must pass its own gate: it derives the needle instead of writing it."""
    text = HOOK.read_text(encoding="utf-8")
    assert NEEDLE not in text, "the hook hardcodes the very path it exists to catch"
    assert "id -un" in text
