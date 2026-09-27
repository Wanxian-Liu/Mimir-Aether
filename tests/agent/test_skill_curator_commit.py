"""skill_curator dormant/revive moves must leave a clean work tree.

Root cause (2026-09-21..28): `capsulize_and_dormant` relocates the skill dir
with `shutil.move` and never commits, so the relocation sat as an uncommitted
`D` + `??` pair and the "clean worktree" completion criterion silently stopped
holding. The differential below proves the helper is what makes it clean.
"""
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import skill_curator as C  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _git(repo, *args):
    env = {**os.environ, **GIT_ENV}
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, env=env)


def _dirty(repo) -> str:
    return _git(repo, "status", "--porcelain").stdout.strip()


def test_outside_repo_is_reported_not_raised(tmp_path):
    assert C._git_commit_skill_move([str(tmp_path / "nope")], "x").startswith("skipped")


def test_move_is_committed_and_tree_goes_clean(tmp_path, monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)
    src = tmp_path / "skills" / "mimiraether" / "alpha"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("x", encoding="utf-8")
    assert _git(tmp_path, "init", "-q").returncode == 0
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")

    dst = tmp_path / "skills" / ".dormant" / "mimiraether" / "alpha"
    dst.parent.mkdir(parents=True)
    shutil.move(str(src), str(dst))

    # controlled differential: the raw move leaves the tree dirty
    assert _dirty(tmp_path), "precondition: raw shutil.move leaves D + ??"

    monkeypatch.setattr(C, "SKILLS_ROOT", str(tmp_path / "skills"))
    result = C._git_commit_skill_move([str(src), str(dst)], "chore: dormant alpha")

    assert result == "committed", result
    assert _dirty(tmp_path) == ""
    assert "dormant alpha" in _git(tmp_path, "log", "-1", "--oneline").stdout
