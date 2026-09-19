"""F1/S2 回归：长条目收缩必须**保尾**（2026-09-19 · 刘哥批）。

为什么专门测尾部：旧实现是 300 字符**纯头部**截断，尾部（路径/命令/判据/数字）被静默
丢掉且不可逆 —— 盘上实证 MEMORY.md 现存 45 处 `(truncated)` 且 5 个备份全带标记
⇒ 无干净源可恢复。所以「尾部不丢」是本改动的**唯一验收点**，必须由测试钉死。
"""

from __future__ import annotations

import pytest

from tools.memory_tool import (
    MAX_ENTRY_CHARS,
    TRUNC_HEAD_RATIO,
    TRUNC_MARKER,
    TRUNC_TAIL_RATIO,
    shrink_long_entry,
)

TAIL_SENTINEL = "TAIL-KEY: effective_window_tokens=300000 / tuned_thresholds.json"
HEAD_SENTINEL = "HEAD-SENTINEL-12345 "


def test_short_entry_untouched():
    entry = "短条目：环境 = Linux；cwd 已知。"
    out, changed = shrink_long_entry(entry)
    assert (out, changed) == (entry, False)
    assert TRUNC_MARKER not in out


def test_boundary_equal_to_limit_untouched():
    entry = "x" * MAX_ENTRY_CHARS
    out, changed = shrink_long_entry(entry)
    assert changed is False and out == entry


def test_long_entry_keeps_tail_sentinel():
    entry = HEAD_SENTINEL + ("y" * 3000) + " " + TAIL_SENTINEL
    out, changed = shrink_long_entry(entry)
    assert changed is True
    # 核心验收：尾部判据仍在，且仍在**结尾**（不是被塞到中间）
    assert out.endswith(TAIL_SENTINEL)


def test_long_entry_keeps_head_prefix():
    entry = HEAD_SENTINEL + ("z" * 3000) + " " + TAIL_SENTINEL
    out, changed = shrink_long_entry(entry)
    assert changed is True
    assert out.startswith(HEAD_SENTINEL.strip())


def test_marker_present_and_size_bounded():
    entry = "a" * 5000 + " " + TAIL_SENTINEL
    out, changed = shrink_long_entry(entry)
    assert changed is True
    assert TRUNC_MARKER in out
    expected_max = int(MAX_ENTRY_CHARS * TRUNC_HEAD_RATIO) + len(TRUNC_MARKER) + int(
        MAX_ENTRY_CHARS * TRUNC_TAIL_RATIO
    )
    assert len(out) <= expected_max + 2


@pytest.mark.parametrize("n", [MAX_ENTRY_CHARS + 1, MAX_ENTRY_CHARS + 8, 1400, 3000])
def test_never_grows(n):
    """不变长守卫：截断后绝不比原文更长（否则「省空间」反而变负）。"""
    entry = "b" * (max(0, n - 1)) + "."
    out, _changed = shrink_long_entry(entry)
    assert len(out) <= len(entry)


def test_no_space_long_entry_still_shrinks():
    """无空白/无句号的长条目（如长哈希串）也必须能收缩且保尾。"""
    entry = "c" * 4000
    out, changed = shrink_long_entry(entry)
    assert changed is True
    assert len(out) < len(entry)


def test_threshold_is_injectable():
    """阈值在**调用时刻**读取（可注入），不是定义时绑定 —— 否则调参会静默失效。"""
    entry = "d" * 200
    assert shrink_long_entry(entry)[1] is False
    out, changed = shrink_long_entry(entry, max_chars=100)
    assert changed is True and len(out) < len(entry)


def test_old_behavior_would_have_lost_tail():
    """对照：旧的 300 字符纯头部截断**必然**丢尾部 —— 钉住「为什么改」。"""
    entry = HEAD_SENTINEL + ("y" * 3000) + " " + TAIL_SENTINEL
    legacy = entry[:300] + " [...] (truncated)"
    assert TAIL_SENTINEL not in legacy
    out, _ = shrink_long_entry(entry)
    assert TAIL_SENTINEL in out
