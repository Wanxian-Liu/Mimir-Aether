"""X3-b: ``install-git-hooks.sh`` must never silently overwrite a repo's hook.

The X3 audit found the old installer did a bare ``cp`` -- installing into
``~/wiki`` (which carries its own ``.contracts/`` hook) would have destroyed it
with no backup. These tests lock in detect -> backup -> chain.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-git-hooks.sh"

FOREIGN_HOOK = """#!/usr/bin/sh
# a repository's own hook; installation must preserve it, not clobber it
echo foreign-hook-ran >> "$(git rev-parse --show-toplevel)/foreign.log"
exit 0
"""


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def _git(repo, *args):
    result = _run(["git", *args], repo)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def _hooks_dir(repo: Path) -> Path:
    out = _run(["git", "rev-parse", "--git-path", "hooks"], repo).stdout.strip()
    return Path(out) if out.startswith("/") else repo / out


def _commit_env(repo: Path) -> dict:
    return {**os.environ, "MIMIR_GIT_COMMIT_AUDIT_LOG": str(repo / "commit-audit.jsonl")}


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "target"
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "config", "user.name", "Tester")
    _git(path, "config", "user.email", "tester@example.com")
    _git(path, "config", "commit.gpgsign", "false")
    return path


def _install(repo: Path):
    return _run(["sh", str(INSTALLER), "--repo", str(repo)], REPO_ROOT)


def _commit(repo: Path, message: str = "x"):
    (repo / "a.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    return subprocess.run(["git", "commit", "-m", message], cwd=str(repo),
                          capture_output=True, text=True, env=_commit_env(repo))


def test_foreign_hook_is_backed_up_preserved_and_still_runs(repo):
    hooks = _hooks_dir(repo)
    (hooks / "pre-commit").write_text(FOREIGN_HOOK, encoding="utf-8")
    (hooks / "pre-commit").chmod(0o755)

    result = _install(repo)
    assert result.returncode == 0, result.stderr

    backups = sorted(hooks.glob("pre-commit.bak-*"))
    assert len(backups) == 1, "existing hook must be backed up, not replaced"
    assert backups[0].read_text(encoding="utf-8") == FOREIGN_HOOK
    assert (hooks / "pre-commit-local").read_text(encoding="utf-8") == FOREIGN_HOOK
    assert (hooks / "pre-commit-mimir-audit").exists()
    assert "MimirAether hook chain" in (hooks / "pre-commit").read_text(encoding="utf-8")

    committed = _commit(repo)
    assert committed.returncode == 0, committed.stderr
    assert (repo / "foreign.log").exists(), "preserved hook did not run"
    records = [json.loads(line) for line in
               (repo / "commit-audit.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    actions = [r["action"] for r in records]
    # Both hooks share ONE audit stream (A2, 2026-09-13): pre-commit writes
    # `commit`, commit-msg writes `signature`. Assert on membership, not on the
    # last line -- assuming "the last record is the pre-commit one" made this
    # test fail the moment a second hook joined the same stream.
    assert "commit" in actions, "pre-commit audit hook did not run"
    assert "signature" in actions, "commit-msg attribution hook did not run"


def test_blocking_own_hook_still_blocks_the_commit(repo):
    """The chain must propagate the preserved hook's non-zero status."""
    hooks = _hooks_dir(repo)
    (hooks / "pre-commit").write_text("#!/usr/bin/sh\nexit 1\n", encoding="utf-8")
    (hooks / "pre-commit").chmod(0o755)

    assert _install(repo).returncode == 0
    blocked = _commit(repo)
    assert blocked.returncode != 0


def test_fresh_repo_gets_chain_without_backup(repo):
    assert _install(repo).returncode == 0
    hooks = _hooks_dir(repo)
    assert list(hooks.glob("pre-commit.bak-*")) == []
    assert not (hooks / "pre-commit-local").exists()
    assert "MimirAether hook chain" in (hooks / "pre-commit").read_text(encoding="utf-8")
    assert _commit(repo).returncode == 0


def test_second_run_is_idempotent(repo):
    """Re-installing refreshes the audit hook and leaves the preserved hook alone."""
    hooks = _hooks_dir(repo)
    (hooks / "pre-commit").write_text(FOREIGN_HOOK, encoding="utf-8")
    (hooks / "pre-commit").chmod(0o755)

    assert _install(repo).returncode == 0
    first_audit = (hooks / "pre-commit-mimir-audit").read_text(encoding="utf-8")

    result = _install(repo)
    assert result.returncode == 0, result.stderr
    assert "already a Mimir chain" in result.stdout
    assert len(list(hooks.glob("pre-commit.bak-*"))) == 1, "no second backup on re-run"
    assert (hooks / "pre-commit-local").read_text(encoding="utf-8") == FOREIGN_HOOK
    assert (hooks / "pre-commit-mimir-audit").read_text(encoding="utf-8") == first_audit


def test_no_backup_flag_skips_the_record(repo):
    hooks = _hooks_dir(repo)
    (hooks / "pre-commit").write_text(FOREIGN_HOOK, encoding="utf-8")
    (hooks / "pre-commit").chmod(0o755)

    env = {**os.environ, "MIMIR_HOOKS_NO_BACKUP": "1"}
    result = subprocess.run(["sh", str(INSTALLER), "--repo", str(repo)],
                            cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert list(hooks.glob("pre-commit.bak-*")) == []
    assert (hooks / "pre-commit-local").read_text(encoding="utf-8") == FOREIGN_HOOK
