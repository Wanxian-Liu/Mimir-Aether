"""B 档 #17 · 梦境蒸馏取数面改指向 memories/MEMORY.md —— 纯函数级回归 + dry-run 集成。

纪律：用例全部真跑（无「跳过」标记类字样）；不调 LLM
（dry_run 在 _run_distillation 最前短路）；不写真实 home（全部用 tmp_path）。
"""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent import dream_memory as dm


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _empty_persistent_home(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "memories").mkdir()
    pj = tmp_path / "data" / "persistent.json"
    pj.write_text(json.dumps({"memory": {"key_decisions": [], "learned_patterns": []}}),
                  encoding="utf-8")
    return pj


def test_persistent_wins_when_arrays_nonempty():
    data = {"memory": {"key_decisions": [{"decision": "D1"}], "learned_patterns": []}}
    text, source = dm.build_distillation_input(data, "# MEM\n§\n正文")
    assert source == dm._DISTILL_SOURCE_PERSISTENT
    assert "D1" in text
    assert "正文" not in text


def test_falls_back_to_memory_md_when_persistent_empty():
    data = {"memory": {"key_decisions": [], "learned_patterns": []}}
    text, source = dm.build_distillation_input(data, "# MEM\n§\n正文")
    assert source == dm._DISTILL_SOURCE_MEMORY_MD
    assert text.startswith("# MEM")


def test_none_when_both_empty():
    assert dm.build_distillation_input({"memory": {}}, "") == ("", dm._DISTILL_SOURCE_NONE)
    assert dm.build_distillation_input({}, "   \n  ") == ("", dm._DISTILL_SOURCE_NONE)
    assert dm.build_distillation_input({"memory": {"key_decisions": []}}, None) == ("", dm._DISTILL_SOURCE_NONE)


def test_metrics_counts_chars_lines_segments():
    text = "a\n\n§\nb\n§\n"
    m = dm.distillation_input_metrics(text)
    assert m["chars"] == len(text)
    assert m["lines"] == 4
    assert m["segments"] == 2


def test_memory_markdown_path_follows_mimir_home(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    assert dm._memory_markdown_path() == os.path.join(str(tmp_path), "memories", "MEMORY.md")


def test_load_memory_markdown_missing_is_empty_not_raise(tmp_path):
    assert dm._load_memory_markdown(str(tmp_path / "absent.md")) == ""


def test_dry_run_persistent_empty_falls_back_and_writes_nothing(monkeypatch, tmp_path):
    """臂 B：空 persistent + 真 MEMORY.md ⇒ 输入 > 0；dry-run 零写盘。"""
    pj = _empty_persistent_home(tmp_path)
    (tmp_path / "memories" / "MEMORY.md").write_text("# MEM\n§\n正文一条", encoding="utf-8")
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    before = _sha(pj)
    ok, report = asyncio.run(dm.run_dream_cycle(dry_run=True))
    assert ok is True
    assert "输入: " in report, report
    assert "输入: 0 字符" not in report, report
    assert _sha(pj) == before
    assert not (tmp_path / "data" / ".distilled").exists()


def test_dry_run_both_empty_reports_no_content_and_writes_nothing(monkeypatch, tmp_path):
    """臂 A 语义保留：两皆空 ⇒ 判「无内容」且不写盘。"""
    pj = _empty_persistent_home(tmp_path)
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    before = _sha(pj)
    ok, report = asyncio.run(dm.run_dream_cycle(dry_run=True))
    assert ok is True
    assert "没有记忆条目需要蒸馏" in report, report
    assert _sha(pj) == before
    assert not (tmp_path / "data" / ".distilled").exists()
