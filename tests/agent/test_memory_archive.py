"""B8 归档层读入口测试（agent/memory_archive.py）。

全部用 tmp_path，不触碰生产记忆目录（fixture 覆盖 _memories_dir）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load():
    spec = importlib.util.spec_from_file_location(
        "memory_archive_under_test", str(REPO / "agent" / "memory_archive.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENTRY_A = "近期部署状态（2026-07-15 确认）：\n- runtime 常驻，不需要部署"
ENTRY_B = "研究树#11 addyosmani/agent-skills (78K stars) 完整吸收。24 skill 交叉对比完成。"
ENTRY_C = "Session 2026-07-26 未完成待办：\n1. wiki 卡片\n2. cross-agent 通信"


def _write_archive(root: Path, blocks) -> None:
    d = root / "memories"
    (d / "archive").mkdir(parents=True, exist_ok=True)
    body = ["# MEMORY.md 归档层 L3\n", "<!-- b8-archive: l3 -->\n"]
    for anchor, payload in blocks:
        body.append("<!-- anchor: %s -->\n" % anchor)
        body.append("<!-- sha256: deadbeef -->\n")
        body.append("<!-- folded: 2026-09-13 | from: memories/MEMORY.md -->\n")
        body.append(payload + "\n\n")
    (d / "archive" / "MEMORY.archive-l3.md").write_text("".join(body), encoding="utf-8")


def _write_manifest(root: Path, anchors) -> None:
    import json

    d = root / "memories"
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory_anchors.json").write_text(
        json.dumps({"version": 1, "anchors": anchors}, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture()
def ma(tmp_path, monkeypatch):
    mod = _load()
    root = tmp_path / "mimir_home"
    root.mkdir()
    _write_archive(root, [("a-1", ENTRY_A), ("a-2", ENTRY_B), ("a-3", ENTRY_C)])
    _write_manifest(root, {
        "a-1": {"sha256": "x", "chars": len(ENTRY_A), "first_line": ENTRY_A.split("\n")[0]},
        "a-2": {"sha256": "y", "chars": len(ENTRY_B), "first_line": ENTRY_B.split("\n")[0]},
    })
    mod._memories_dir = lambda: root / "memories"
    return mod



def test_parse_blocks_are_verbatim(ma):
    blocks = ma.parse_archive_blocks()
    assert [a for a, _ in blocks] == ["a-1", "a-2", "a-3"]
    assert blocks[0][1] == ENTRY_A
    assert blocks[2][1] == ENTRY_C


def test_read_by_anchor_exact(ma):
    assert ma.read_memory_archive(anchor="a-2") == ENTRY_B
    assert ma.read_memory_archive(anchor="nope") is None


def test_read_by_section_id_prefix(ma):
    got = ma.read_memory_archive(section_id="近期部署状态")
    assert got == ENTRY_A


def test_read_by_query_substring(ma):
    got = ma.read_memory_archive(query="addyosmani")
    assert got == ENTRY_B


def test_no_hit_returns_none_not_empty_string(ma):
    assert ma.read_memory_archive(query="zzz-absent-zzz") is None
    assert ma.read_memory_archive() is None
    assert ma.read_memory_archive(section_id="") is None


def test_limit_caps_multi_hit(ma):
    got = ma.read_memory_archive(query="2026-", limit=1)
    assert got is not None and "---" not in got
    got2 = ma.read_memory_archive(query="2026-", limit=10)
    assert got2 is not None and got2.count("---") >= 1


def test_archive_stats_flags_orphan_block(ma):
    stats = ma.archive_stats()
    assert stats["blocks"] == 3
    assert stats["manifest_anchors"] == 2
    assert stats["blocks_without_manifest"] == ["a-3"]
    assert stats["manifest_anchors_without_block"] == []
    assert stats["archive_exists"] is True


def test_missing_archive_is_safe(tmp_path):
    mod = _load()
    root = tmp_path / "empty"
    root.mkdir()
    mod._memories_dir = lambda: root / "memories"
    assert mod.parse_archive_blocks() == []
    assert mod.read_memory_archive(query="x") is None
    assert mod.load_anchor_index() == {}
    assert mod.archive_stats()["archive_exists"] is False


def test_broken_manifest_json_is_safe(tmp_path):
    mod = _load()
    root = tmp_path / "broken"
    (root / "memories").mkdir(parents=True)
    (root / "memories" / "memory_anchors.json").write_text("{not json", encoding="utf-8")
    mod._memories_dir = lambda: root / "memories"
    assert mod.load_anchor_index() == {}
    assert mod.list_anchors() == []


def test_list_anchors_round_trips_meta(ma):
    rows = ma.list_anchors()
    anchors = {r["anchor"] for r in rows}
    assert anchors == {"a-1", "a-2"}
    assert all("chars" in r and "first_line" in r for r in rows)


def test_module_is_read_only_over_archive(ma, tmp_path):
    """读入口不得改写归档层/注入层（CR7 端口，不是写入器）。"""
    arch = ma.archive_path()
    before = arch.read_bytes()
    ma.read_memory_archive(query="2026-")
    ma.archive_stats()
    assert arch.read_bytes() == before
