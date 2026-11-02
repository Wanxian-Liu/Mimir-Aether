"""回归：skill 解析器必须是「一个源」且退役技能不可见。

背景（2026-11-02 L2 审计）:
  - ``_find_skill`` 原先只扫 ``agent.skill_utils.get_all_skills_dirs()``，该函数在本机解析到
    遗留空目录 ``~/.mimir/skills``（0 个 SKILL.md）⇒ 对**任何真实技能**都返回 None，
    连带 ``gateway.run._has_setup_skill`` 恒 False。
  - ``suggest_skill_names`` 用的是另一套源（会看到 200+ 技能）⇒ 两个解析器互相矛盾。
  - 修法：两者共用 ``_iter_skill_md()``；只过滤 ``.worktrees``（另一个 checkout），
    **不过滤 ``.dormant``** —— 实证：98 个 SKILL.md 在 ``skills/.dormant``，其中
    ``mimir-true-self`` / ``using-agent-skills`` / ``wiki-knowledge-ingest`` 三个带
    ``auto_load: true`` 每轮注入 ⇒ 是「cold 但仍活」，滤掉会让 skill_manage 对活技能报 not found。

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


def test_find_skill_sees_dormant_skill(fake_tree):
    """正控：``.dormant/`` 是「cold 但仍活」——必须能找到（否则活技能被 manage 报 not found）。"""
    hit = smt._find_skill("beta-skill")
    assert hit is not None
    assert hit["path"].name == "beta-skill"


def test_find_skill_hides_worktree_copy(fake_tree):
    """负控：``.worktrees/`` 下的重复副本不得被当成「已安装」。"""
    assert smt._find_skill("gamma-skill") is None


def test_find_and_suggest_share_one_resolver(fake_tree):
    """一致性：find 与 suggest 必须看到同一个集合（这是原缺陷的直接回归）。"""
    names = {n for _m, n in smt._iter_skill_md()}
    assert names == {"alpha-skill", "beta-skill"}, names
    assert "alpha-skill" in smt.suggest_skill_names("alpha-skll")
    assert "beta-skill" in smt.suggest_skill_names("beta-skll")


def test_iter_skill_md_never_yields_hidden_paths():
    """不 monkeypatch 的真库检查：产出里不得含 .dormant/.worktrees 相对路径。"""
    roots = smt._iter_skill_dirs()
    yielded = list(smt._iter_skill_md())
    assert yielded, "真库应至少产出一个技能（否则判据无意义）"
    for md, _name in yielded:
        root = next(r for r in roots if str(md).startswith(str(r) + "/"))
        rel_parts = md.relative_to(root).parts
        assert ".worktrees" not in rel_parts, rel_parts


def test_roots_pin_repo_skills():
    """钉根清单（仓内侧）：仓库自带 skills 目录必须在解析根里。

    这条不依赖家目录，CI 上稳定。
    """
    expected = str(REPO / "skills")
    roots = [str(r) for r in smt._iter_skill_dirs()]
    assert expected in roots, f"expected {expected} in {roots}"


def test_roots_are_not_vacuous():
    """钉「根清单非空转」：至少有一个根真的装着 SKILL.md。

    原缺陷的形态就是「根清单指向一个 0 个 SKILL.md 的遗留目录」——只看路径是否
    在清单里拦不住它（路径清单可以包含空目录）。这里改钉内容。
    """
    md = [m for m, _n in smt._iter_skill_md()]
    assert md, "解析器一个技能都没看到（根清单空转 = 原缺陷形态）"


def test_find_skill_agrees_with_shared_enumerator():
    """核心回归：``_find_skill`` 必须与共享枚举器看到同一集合。

    这是原缺陷的直接判据——旧实现里 ``_find_skill`` 走
    ``get_all_skills_dirs()``（本机 0 个 SKILL.md），而枚举器看到 200+，
    于是「枚举得到、find 找不到」。
    """
    names = [n for _m, n in smt._iter_skill_md()]
    assert names, "枚举器为空，本用例无意义"
    for name in names[:20]:
        hit = smt._find_skill(name)
        assert hit is not None, f"{name} 枚举得到但 find 找不到"
        assert hit["path"].name == name
