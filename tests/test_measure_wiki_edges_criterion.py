"""回归用例：measure_wiki_edges 的 --criterion 必须改变**头条指标**(islands)。

事故（2026-11-11 内部三席会 A/C 席各自独立发现）：
    islands = n - union_ge1   ← 恒用 union 计算
    ⇒ --criterion body|fm|union 三次输出逐字节相同，判据开关对头条指标无效。
    ⇒ 上一版 selftest 只断言中间字段(body_ge1/union_ge1)，故 bug 逃逸。

本用例的鉴别力：把 islands 改回恒用 union，第一个断言必失。
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
    # a: 正文 2 链；无 fm 边
    (w / "concepts/a.md").write_text("---\ntitle: a\n---\n[[x]] [[y]]\n", encoding="utf-8")
    # b: 仅 frontmatter 1 边
    (w / "concepts/b.md").write_text(
        '---\ntitle: b\nrelations:\n  - type: related_to\n    target: "[[a]]"\n---\nno link\n',
        encoding="utf-8")
    # c: 真孤岛
    (w / "concepts/c.md").write_text("---\ntitle: c\n---\nno link\n", encoding="utf-8")
    # d: 正文 1 链
    (w / "concepts/d.md").write_text("---\ntitle: d\n---\n[[b]]\n", encoding="utf-8")
    return w


def test_criterion_has_discriminating_power(tmp_path):
    """三口径头条指标必须互不相同——这就是当年的负控样本。"""
    w = _fixture(tmp_path)
    body = m.measure(w, "single", "body")
    fm = m.measure(w, "single", "fm")
    union = m.measure(w, "single", "union")

    got = {body["islands"], fm["islands"], union["islands"]}
    assert len(got) == 3, (
        f"criterion 对 islands 无鉴别力：body={body['islands']} "
        f"fm={fm['islands']} union={union['islands']}（相等即开关已死）"
    )


def test_islands_follow_criterion_exactly(tmp_path):
    w = _fixture(tmp_path)
    n = m.measure(w, "single", "body")["cards"]
    assert n == 4
    for crit, linked in (("body", 2), ("fm", 1), ("union", 3)):
        r = m.measure(w, "single", crit)
        assert r["islands"] == n - linked, f"{crit}: islands={r['islands']} want {n - linked}"


def test_islands_by_source_reported(tmp_path):
    """A 席 b1：分源读数必须在同一份输出里可见（禁跨口径混比）。"""
    w = _fixture(tmp_path)
    r = m.measure(w, "single", "union")
    by = r["islands_by_source"]
    assert set(by) == {"body", "fm", "union"}
    assert by["union"] == r["islands"], "头条指标必须与分源读数一致"
    assert by["body"] != by["fm"], "两源若同值，需人工确认不是巧合"


def test_unknown_criterion_rejected(tmp_path):
    w = _fixture(tmp_path)
    with pytest.raises(ValueError):
        m.measure(w, "single", "nonsense")
