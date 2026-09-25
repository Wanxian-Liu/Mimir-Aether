"""R6 follow-up (2026-09-26): real-object arms for the pre-push published scan.

Why these exist
  The 18 shape arms in test_pre_push_path_leak.py all passed on the day the
  gate was installed -- and they passed while the gate was built on the same
  assumptions the shapes were. The shapes were mine; they were wrong in
  exactly the two ways the audit had found by hand. A fixture set in which
  every arm passes is not evidence that the gate sees the real thing, so
  these arms feed the gate the REAL values found on 2026-09-25/26.

What is locked in here
  * the real Feishu chat id, recovered from this repository history, is
    BLOCKED; a masked twin at the same position is ALLOWED, so "blocks
    everything" stays excluded
  * the real home-path line from the local worktree file is BLOCKED; the
    abstracted twin is ALLOWED
  * both real values are recovered at run time and never written down here:
    a test that spelled the leak out would itself be the leak

Honest limit
  Arm 2 skips when the local worktree file is absent. A skip is reported as
  a skip, not as a pass -- if the object ever disappears, that shows up in
  the pytest summary instead of turning silently green.
"""
import getpass
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-git-hooks.sh"
HOOK = REPO_ROOT / "scripts" / "git-hooks" / "pre-push"
ZERO = "0" * 40

NEEDLE = "/home/" + getpass.getuser()
CHAT_ID_RE = re.compile(r"oc_[0-9a-f]{32}")


# Files that carried a real chat id somewhere in this repository history.
# Scanning their FULL history rather than the current tree is the whole point:
# the current tree was already cleaned, which is what made the shape arms
# look sufficient.
CARRIERS = (
    "config.example.yaml",
    "docs/phase0/mimir-away-evidence.md",
    "tests/agent/test_cross_session_retrieval_feishu.py",
)


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


def _env(extra=None):
    env = {**os.environ, "MIMIR_AGENT_ID": "mimir"}
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
    return {"remote": remote, "work": work}


def _hook(clone, ref_lines, extra_env=None):
    stdin = "".join(line + "\n" for line in ref_lines)
    return _run(["sh", str(HOOK), "origin", str(clone["remote"])], clone["work"],
                env=_env(extra_env), stdin=stdin)


def _push_new_branch(clone, extra_env=None):
    head = _git(clone["work"], "rev-parse", "HEAD").stdout.strip()
    return _hook(clone, ["refs/heads/main %s refs/heads/main %s" % (head, ZERO)], extra_env)


def _real_chat_id_from_history():
    """Recover the real value out of git; return None when history is clean."""
    for name in CARRIERS:
        revs = _run(["git", "rev-list", "--all", "--", name], REPO_ROOT)
        if revs.returncode != 0:
            continue
        for rev in revs.stdout.split():
            show = _run(["git", "show", "%s:%s" % (rev, name)], REPO_ROOT)
            if show.returncode != 0:
                continue
            hit = CHAT_ID_RE.search(show.stdout)
            if hit:
                return hit.group(0)
    return None


def _real_home_path_line():
    """A line from the local (gitignored) worktree file that carries the needle."""
    root = REPO_ROOT / ".worktrees"
    if not root.is_dir():
        return None
    for path in sorted(root.rglob("*.json"))[:200]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            if NEEDLE in line and len(line.strip()) < 400:
                return line.strip()
    return None


def test_real_historical_chat_id_is_blocked(clone):
    """The ACTUAL identifier found in history, not a shape built from it."""
    value = _real_chat_id_from_history()
    if value is None:
        pytest.skip("no real chat id remains in this repository history")
    _commit_file(clone["work"], "cfg.yaml", "chat_id: %s\n" % value, "real id")
    result = _push_new_branch(clone)
    assert result.returncode != 0, "the real chat id was allowed through:\n" + result.stdout + result.stderr


def test_masked_twin_at_the_same_position_passes(clone):
    """Negative twin: same line, same position, value masked -> allowed."""
    value = _real_chat_id_from_history()
    if value is None:
        pytest.skip("no real chat id remains in this repository history")
    masked = value[:5] + "x" * 32
    assert masked != value
    assert not CHAT_ID_RE.fullmatch(masked), "the twin must not itself be a real-shaped id"
    _commit_file(clone["work"], "cfg.yaml", "chat_id: %s\n" % masked, "masked twin")
    result = _push_new_branch(clone)
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_worktree_home_path_line_is_blocked(clone):
    """The real leaked line shape: a JSON value holding an absolute home path."""
    line = _real_home_path_line()
    if line is None:
        pytest.skip("the local worktree file carrying the home path is absent")
    _commit_file(clone["work"], "map.json", line + "\n", "real worktree line")
    result = _push_new_branch(clone)
    assert result.returncode != 0, "the real home-path line was allowed through:\n" + result.stdout + result.stderr


def test_abstracted_twin_of_that_line_passes(clone):
    """Negative twin: identical line with the account name abstracted -> allowed."""
    line = _real_home_path_line()
    if line is None:
        pytest.skip("the local worktree file carrying the home path is absent")
    twin = line.replace(NEEDLE, "/home/<user>")
    assert NEEDLE not in twin
    _commit_file(clone["work"], "map.json", twin + "\n", "abstracted twin")
    result = _push_new_branch(clone)
    assert result.returncode == 0, result.stdout + result.stderr


def test_this_file_carries_no_literal_of_the_real_values():
    """Self-check: the regression file must not become the new leak."""
    source = Path(__file__).read_text(encoding="utf-8")
    assert NEEDLE not in source, "the account name is spelled out in this file"
    assert not CHAT_ID_RE.search(source), "a real-shaped chat id is spelled out in this file"
