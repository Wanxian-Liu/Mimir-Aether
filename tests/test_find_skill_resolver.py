"""回归：skill 解析器必须是「一个源」且退役技能不可见。

背景（2026-11-02 L2 审计）:
  - ``_find_skill`` 原先只扫 ``agent.skill_utils.get_all_skills_dirs()``，该函数在本机解析到
    遗留空目录 ``~/.mimir/skills``（0 个 SKILL.md）⇒ 对**任何真实技能**都返回 None，
    连带 ``gateway.run._has_setup_skill`` 恒 False。
  - ``suggest_skill_names`` 用的是另一套源（会看到 200+ 技能）⇒ 两个解析器互相矛盾。
  - 修法：两者共用 ``_iter_skill_md()``，并在**相对 skills 根**的路径上过滤 ``.dormant`` /
    ``.worktrees``（退役/重复副本），同时不误伤根路径之上的合法点段（如 ``~/.mimiraether``）。

本文件用 tmp 目录合成技能树，不依赖本机技能内容。
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import tools.skill_manager_tool as smt


def _make_skill(root: Path, *parts: str) -> Path:
    d = root.joinpath(*parts)
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n\nbody\n", encoding="utf-8")
    return d


@pytest.fixture()
def fake_tree(tmp_path, monkeypatch):
    """一个 skills 根，内含：正常技能 / .dormant 退役副本 / .worktrees 重复副本。"""
    root = tmp_path / "skills"
    _make_skill(root, "cat", "alpha-skill")
    _make_skill(root, ".dormant", "cat", "beta-skill")
    _make_skill(root, ".worktrees", "wt1", "catskills", "gamma-skill")
    monkeypatch.setattr(smt, "_iter_skill_dirs", lambda: [root])
    return root


def test_find_skill_finds_active_skill(fake_tree):
    """正控：正常路径下的技能必须能找到（否则修复等于把整套 find 关掉）。"""
    hit = smt._find_skill("alpha-skill")
    assert hit is not None
    assert hit["path"].name == "alpha-skill"


def test_find_skill_hides_dormant_skill(fake_tree):
    """负控：``.dormant/`` 下的退役技能不得被当成「已安装」。"""
    assert smt._find_skill("beta-skill") is None


def test_find_skill_hides_worktree_copy(fake_tree):
    """负控：``.worktrees/`` 下的重复副本不得被当成「已安装」。"""
    assert smt._find_skill("gamma-skill") is None


def test_find_and_suggest_share_one_resolver(fake_tree):
    """一致性：find 与 suggest 必须看到同一个集合（这是原缺陷的直接回归）。"""
    names = {n for _m, n in smt._iter_skill_md()}
    assert names == {"alpha-skill"}, names
    assert "alpha-skill" in smt.suggest_skill_names("alpha-skll")
    assert "beta-skill" not in smt.suggest_skill_names("beta-skll")


def test_iter_skill_md_never_yields_hidden_paths():
    """不 monkeypatch 的真库检查：产出里不得含 .dormant/.worktrees 相对路径。"""
    roots = smt._iter_skill_dirs()
    yielded = list(smt._iter_skill_md())
    assert yielded, "真库应至少产出一个技能（否则判据无意义）"
    for md, _name in yielded:
        root = next(r for r in roots if str(md).startswith(str(r) + "/"))
        rel_parts = md.relative_to(root).parts
        assert ".worktrees" not in rel_parts
        assert not any(p.startswith(".") for p in rel_parts), rel_parts
