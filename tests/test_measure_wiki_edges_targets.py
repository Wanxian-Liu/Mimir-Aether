"""回归用例：measure_wiki_edges --check-targets 目标存在性校验。

判据顺序 = 负控先行（幽灵必须报红），再正控（补卡即放行）——防「恒红」与「恒绿」两种死法。
鉴别力：把 rc 改成恒 0，负控第一条必失；把 rc 改成恒 1，正控必失。
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import measure_wiki_edges as m  # noqa: E402


def _fixture(w: Path) -> Path:
    for d in ("concepts", "entities", "discussions"):
        (w / d).mkdir(parents=True, exist_ok=True)
    (w / "concepts/real.md").write_text("---\ntitle: real\n---\nno link\n", encoding="utf-8")
    (w / "concepts/src.md").write_text(
        "---\ntitle: src\nrelations:\n"
        "  - type: related_to\n    target: \"[[ghost-bracket]]\"\n"
        "  - type: related_to\n    target: concepts/ghost-path\n"
        "  - type: related_to\n    target: ghost-bare\n"
        "---\n[[real]] [[ghost-body]]\n", encoding="utf-8")
    return w


def test_ghost_targets_reported_red(tmp_path):
    """负控：四种写法的幽灵目标都必须被报出，且 rc=1。"""
    w = _fixture(tmp_path)
    r, rc = m.check_targets(w, "single", "union")
    assert rc == 1
    for name in ("ghost-body", "ghost-bracket", "concepts/ghost-path", "ghost-bare"):
        assert name in r["ghosts"], name
    assert r["ghost_targets"] == 4
    assert "real" not in r["ghosts"]


def test_positive_control_passes_after_creating_cards(tmp_path):
    """正控：同一条命令，补上卡后幽灵清零、rc=0（证明红是内容驱动）。"""
    w = _fixture(tmp_path)
    for name in ("ghost-body", "ghost-bracket", "ghost-bare"):
        (w / "concepts" / f"{name}.md").write_text("---\ntitle: x\n---\nno link\n", encoding="utf-8")
    (w / "concepts/ghost-path.md").write_text("---\ntitle: y\n---\nno link\n", encoding="utf-8")
    r, rc = m.check_targets(w, "single", "union")
    assert r["ghost_targets"] == 0
    assert rc == 0


def test_idle_wiki_is_not_green(tmp_path):
    """空转负控：0 个 .md ⇒ rc=3，不许判绿。"""
    (tmp_path / "concepts").mkdir()
    _, rc = m.check_targets(tmp_path, "single", "union")
    assert rc == 3


def test_noncard_targets_exempt_but_counted(tmp_path):
    """URL / memory: / 纯数字 不是卡目标 ⇒ 不判红，但计入 skipped_noncard。"""
    w = tmp_path
    (w / "concepts").mkdir()
    (w / "concepts/c.md").write_text(
        "---\ntitle: c\n---\n[[https://example.com]] [[memory:MEMORY_ID]] [[0, 1]]\n",
        encoding="utf-8")
    r, rc = m.check_targets(w, "single", "union")
    assert r["skipped_noncard"] == 3
    assert r["ghost_targets"] == 0
    assert rc == 0


def test_case_only_mismatch_is_soft_not_red(tmp_path):
    """仅大小写不符 ⇒ ghost_soft（Obsidian 可解析），不进硬幽灵、不判红。"""
    w = tmp_path
    (w / "concepts").mkdir()
    (w / "concepts/CaseCard.md").write_text("---\ntitle: C\n---\nno link\n", encoding="utf-8")
    (w / "concepts/linker.md").write_text("---\ntitle: L\n---\n[[casecard]]\n", encoding="utf-8")
    r, rc = m.check_targets(w, "single", "union")
    assert "casecard" in r["ghost_soft"]
    assert r["ghost_targets"] == 0
    assert rc == 0


def test_code_block_links_not_counted(tmp_path):
    """教学占位在围栏代码块内 ⇒ 不是边（links_checked 与 links_raw 显式分列）。"""
    w = tmp_path
    (w / "concepts").mkdir()
    (w / "concepts/t.md").write_text(
        "---\ntitle: t\n---\n```\n[[tutorial-placeholder]]\n```\n[[real]]\n",
        encoding="utf-8")
    (w / "concepts/real.md").write_text("---\ntitle: r\n---\nno link\n", encoding="utf-8")
    r, rc = m.check_targets(w, "single", "union")
    assert "tutorial-placeholder" not in r["ghosts"]
    assert r["links_raw"] == 2          # 量具口径（不剥代码块）
    assert r["links_checked"] == 1      # 剥后口径
    assert rc == 0


def test_measure_mode_rc_stays_zero(tmp_path):
    """不传 --check-targets 时量具 rc 恒 0（闸不回归量具既有用法）。"""
    w = _fixture(tmp_path)
    r = m.measure(w, "single", "union")
    assert r["cards"] == 2
    assert "ghosts" not in r
