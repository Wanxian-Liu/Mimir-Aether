"""A 方案（2026-11-22）：MEMORY.md 增量合并取数面。

两个变异点必须能打死（否则用例是摆设）：
  M1 空 delta 也走 MERGED  ⇒ test_empty_delta_stays_persistent 必红
  M2 忽略前缀 sha 直接 append ⇒ test_rewritten_md_resends_full 必红
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import agent.dream_memory as dm


def _mem(kd=None):
    return {"memory": {"key_decisions": kd if kd is not None else ["决策A"]}}


def _state_for(text, cursor):
    return {"cursor": cursor, "sha": hashlib.sha256(text[:cursor].encode()).hexdigest()}


# ---------- memory_md_delta 纯函数 ----------

def test_first_time_sends_full():
    body = "# MEM\n第一段\n"
    delta, state, mode = dm.memory_md_delta(body, None)
    assert mode == "first"
    assert delta == body
    assert state["cursor"] == len(body)
    assert state["sha"] == hashlib.sha256(body.encode()).hexdigest()


def test_append_only_tail():
    head = "# MEM\n第一段\n"
    body = head + "第二段（新知识）\n"
    delta, state, mode = dm.memory_md_delta(body, _state_for(body, len(head)))
    assert mode == "append"
    assert delta == "第二段（新知识）\n"
    assert state["cursor"] == len(body)


def test_no_change_returns_empty():
    body = "# MEM\n第一段\n"
    delta, state, mode = dm.memory_md_delta(body, _state_for(body, len(body)))
    assert mode == "none"
    assert delta == ""
    assert state["cursor"] == len(body)


def test_rewritten_md_resends_full():
    """M2 变异点：MEMORY.md 被重写（前缀对不上）⇒ 必须全量重发，不能把错位当增量。"""
    old = "# MEM\n旧的第一段\n旧第二段\n"
    new = "# MEM\n提纯后完全不同的内容\n"
    st = {"cursor": len(old), "sha": hashlib.sha256(old.encode()).hexdigest()}
    delta, state, mode = dm.memory_md_delta(new, st)
    assert mode == "rewrite"
    assert delta == new
    assert state["cursor"] == len(new)


def test_empty_body_is_none():
    for b in ("", "   \n  "):
        delta, state, mode = dm.memory_md_delta(b, _state_for("x", 1))
        assert (delta, mode) == ("", "none")
        assert state == {"cursor": 0, "sha": ""}


def test_corrupt_state_treated_as_first():
    body = "# MEM\n正文\n"
    for bad in ({"cursor": "abc"}, {"cursor": -5}, {"sha": 123}, "not-a-dict", 42):
        delta, _, mode = dm.memory_md_delta(body, bad)
        assert mode in ("first", "rewrite"), (bad, mode)
        assert delta == body


# ---------- build_distillation_input_merged 取数面矩阵 ----------

def test_merged_when_primary_and_delta():
    md = "# MEM\n第一段\n新知识X\n"
    head = "# MEM\n第一段\n"
    text, source, state, mode = dm.build_distillation_input_merged(
        _mem(), md, _state_for(md, len(head))
    )
    assert source == dm._DISTILL_SOURCE_MERGED
    assert mode == "append"
    assert "新知识X" in text
    assert "决策A" in text
    assert dm._MEMORY_MD_DELTA_HEADER.strip() in text
    assert state["cursor"] == len(md)


def test_empty_delta_stays_persistent():
    """M1 变异点：无增量时必须报 PERSISTENT，不能挂 MERGED（读数真·语义假）。"""
    md = "# MEM\n第一段\n"
    text, source, _state, mode = dm.build_distillation_input_merged(
        _mem(), md, _state_for(md, len(md))
    )
    assert source == dm._DISTILL_SOURCE_PERSISTENT
    assert mode == "none"
    assert dm._MEMORY_MD_DELTA_HEADER.strip() not in text


def test_md_state_none_equals_legacy():
    """md_state=None ⇒ 关闭增量分支 ⇒ 与旧版逐字一致（兼容闸）。"""
    md = "# MEM\n§\n正文\n"
    merged = dm.build_distillation_input_merged(_mem(), md, None)
    legacy = dm.build_distillation_input(_mem(), md)
    assert merged[:2] == legacy
    assert merged[2] is None and merged[3] == "off"
    assert merged[0] == "# 关键决策\n- 决策A" or "决策A" in merged[0]


def test_legacy_fallback_unchanged():
    """旧行为不变：三数组空 ⇒ 回落 MEMORY.md；皆空 ⇒ none。"""
    assert dm.build_distillation_input({"memory": {}}, "# MEM\n§\n正文") == (
        "# MEM\n§\n正文", dm._DISTILL_SOURCE_MEMORY_MD)
    assert dm.build_distillation_input({"memory": {}}, "") == ("", dm._DISTILL_SOURCE_NONE)


def test_pure_no_side_effect_on_data():
    """纯函数闸：不得就地改 data['memory']（推进游标是调用方写盘后的职责）。"""
    data = _mem()
    snapshot = repr(data)
    dm.build_distillation_input_merged(data, "# MEM\n新\n", None)
    dm.build_distillation_input_merged(data, "# MEM\n新\n", {})
    assert repr(data) == snapshot
    assert dm._DISTILL_MD_STATE_KEY not in data["memory"]
