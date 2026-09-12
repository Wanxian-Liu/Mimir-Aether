"""E2E tests for the foreign-amend guard (Q3-B / B4 / G-5).

Runs the *real* tracked hook (scripts/git-hooks/pre-commit) inside a throwaway
git repo -- no mocking -- because the whole point of B4 is that the rule is a
commit-time gate, not prose. The detection mechanism (git 2.43 does not export
GIT_REFLOG_ACTION to pre-commit; ancestry walk via ps) is exercised for real.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SRC = REPO_ROOT / "scripts" / "git-hooks" / "pre-commit"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update({k: v for k, v in env.items() if v is not None})
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, env=e)


def _make_repo(tmp_path, author="Other Agent", email="other@example.com"):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", author)
    _git(repo, "config", "user.email", email)
    (repo / "a.txt").write_text("one\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _install_hook(repo):
    rel = _git(repo, "rev-parse", "--git-path", "hooks/pre-commit").stdout.strip()
    dest = Path(rel)
    if not dest.is_absolute():
        dest = repo / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HOOK_SRC, dest)
    dest.chmod(0o755)
    return dest


def _switch_identity_to_mimir(repo):
    _git(repo, "config", "user.name", "Mimir")
    _git(repo, "config", "user.email", "mimir@mimiraether.local")
    (repo / "a.txt").write_text("two\n")
    _git(repo, "add", "a.txt")


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _audit(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_hook_file_is_tracked_and_executable():
    assert HOOK_SRC.exists(), "tracked hook missing"
    assert os.access(HOOK_SRC, os.X_OK), "tracked hook is not executable"


def test_foreign_amend_is_blocked_and_head_unchanged(tmp_path):
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _switch_identity_to_mimir(repo)
    audit = tmp_path / "commit-audit.jsonl"
    before = _head(repo)

    proc = _git(repo, "commit", "--amend", "--no-edit",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    assert proc.returncode != 0, f"amend should be blocked, stdout={proc.stdout} stderr={proc.stderr}"
    assert "BLOCKED -- foreign amend" in proc.stderr
    assert _head(repo) == before, "HEAD must not move when the hook blocks"
    outcomes = [r["outcome"] for r in _audit(audit)]
    assert outcomes == ["amend-foreign-blocked"]
    assert _audit(audit)[0]["action"] == "amend"


def test_foreign_amend_with_custom_message_is_also_blocked(tmp_path):
    """`--amend -m X` is the case prepare-commit-msg cannot see -- ancestry
    detection must still catch it."""
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _switch_identity_to_mimir(repo)
    audit = tmp_path / "commit-audit.jsonl"
    before = _head(repo)

    proc = _git(repo, "commit", "--amend", "-m", "rewritten message",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    assert proc.returncode != 0
    assert _head(repo) == before


def test_override_allows_but_traces(tmp_path):
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _switch_identity_to_mimir(repo)
    audit = tmp_path / "commit-audit.jsonl"
    before = _head(repo)

    proc = _git(repo, "commit", "--amend", "--no-edit",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit), "MIMIR_ALLOW_FOREIGN_AMEND": "1"})

    assert proc.returncode == 0, proc.stderr
    assert _head(repo) != before
    assert "override traced" in proc.stderr
    rec = _audit(audit)[0]
    assert rec["outcome"] == "amend-foreign-override"
    assert rec["override"] == "true"


def test_normal_commit_by_mimir_is_allowed_and_traced(tmp_path):
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _git(repo, "config", "user.name", "Mimir")
    _git(repo, "config", "user.email", "mimir@mimiraether.local")
    audit = tmp_path / "commit-audit.jsonl"
    (repo / "b.txt").write_text("new\n")
    _git(repo, "add", "b.txt")

    proc = _git(repo, "commit", "-m", "normal commit",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    assert proc.returncode == 0, proc.stderr
    rec = _audit(audit)[0]
    assert rec["action"] == "commit"
    assert rec["outcome"] == "commit"
    assert rec["committer"].startswith("Mimir")


def test_own_amend_is_allowed(tmp_path):
    """Amending your own commit is legitimate -- the gate must not over-block."""
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _git(repo, "config", "user.name", "Mimir")
    _git(repo, "config", "user.email", "mimir@mimiraether.local")
    audit = tmp_path / "commit-audit.jsonl"
    (repo / "c.txt").write_text("mine\n")
    _git(repo, "add", "c.txt")
    _git(repo, "commit", "-q", "-m", "mine", env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    proc = _git(repo, "commit", "--amend", "--no-edit",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    assert proc.returncode == 0, proc.stderr
    outcomes = [r["outcome"] for r in _audit(audit)]
    assert outcomes == ["commit", "amend-own"]


def test_non_mimir_identity_only_warns(tmp_path):
    """Hermes may land audit segments here with her own identity: allowed,
    but the trail says so (no silent foreign commits)."""
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    audit = tmp_path / "commit-audit.jsonl"
    (repo / "d.txt").write_text("audit\n")
    _git(repo, "add", "d.txt")

    proc = _git(repo, "commit", "-m", "hermes audit segment",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    assert proc.returncode == 0, proc.stderr
    assert "repo default is" in proc.stderr
    assert _audit(audit)[0]["outcome"] == "commit-non-mimir-identity"


def test_no_verify_bypasses_hook_and_writes_no_trace(tmp_path):
    """--no-verify deliberately leaves a gap in the trail: absence is the signal."""
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _switch_identity_to_mimir(repo)
    audit = tmp_path / "commit-audit.jsonl"

    proc = _git(repo, "commit", "--amend", "--no-edit", "--no-verify",
                env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit)})

    assert proc.returncode == 0
    assert _audit(audit) == []


def test_trace_carries_trace_id_and_agent_id(tmp_path):
    repo = _make_repo(tmp_path)
    _install_hook(repo)
    _switch_identity_to_mimir(repo)
    audit = tmp_path / "commit-audit.jsonl"

    _git(repo, "commit", "--amend", "--no-edit",
         env={"MIMIR_GIT_COMMIT_AUDIT_LOG": str(audit),
              "MIMIR_TRACE_ID": "tr_hooktest", "MIMIR_AGENT_ID": "mimir"})

    rec = _audit(audit)[0]
    assert rec["trace_id"] == "tr_hooktest"
    assert rec["agent_id"] == "mimir"
    assert rec["repo"].endswith("repo")
