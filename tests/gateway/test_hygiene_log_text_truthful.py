"""结构闸：卫生压缩日志不得再打印「死文案」百分比（2026-09-16）。

2026-09-16 卫生阈值真源已改为 tuned 键 ``compressor.hygiene_token_threshold``（热调，
不用重启），但日志残留 "(threshold: 85% of 1,048,576 = N tokens)" —— 前半句与真源无关，
在刘哥的 token 观察实验里会直接被误读。本闸盯住这类「显示层与真源脱钩」。
"""
from __future__ import annotations

import pathlib

MIXIN = pathlib.Path(__file__).resolve().parents[2] / "gateway" / "router" / "agent_route_mixin.py"


def test_hygiene_log_prints_only_the_real_threshold() -> None:
    src = MIXIN.read_text(encoding="utf-8")
    assert "(threshold: %s tokens)" in src, "真源阈值未出现在日志文案里"
    assert "%% of %s = %s tokens" not in src, "死文案回退：日志又在打 85% of <ctx> = <n>"
    assert "_hyg_threshold_pct" not in src, "死变量回退：_hyg_threshold_pct 又被引用"


def test_threshold_helper_is_the_only_source() -> None:
    src = MIXIN.read_text(encoding="utf-8")
    assert "_hygiene_token_threshold()" in src, "日志/判定未走 tuned 键真源"
