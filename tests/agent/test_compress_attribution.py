"""T21/D1/D2 [COMPRESS] 归属注入回归测试（2026-09-14）。

这个文件的存在理由是**两个已实测的阻断缺陷**，都必须钉死：

  D1（会把日志整行丢掉）：初版 `_CompressAttributionFilter` 用 `record.getMessage()`
      （已代入实参的成品串）去拼，却把**原始 args** 塞回 `record.args`
      ⇒ 格式符数 ≠ 实参数 ⇒ `TypeError: not all arguments converted during string
      formatting` ⇒ logging 走 handleError ⇒ **该行不入日志**。
      反讽：它要修的是「压缩事件无法归因」，结果把可观测性整个抹掉。

  D2（会打断前缀契约）：注入插在 `[COMPRESS] ` **之后**，破坏
      `[COMPRESS] trigger|skip|result|abort` 锚点。盘上有 4 个真实消费者：
      `scripts/b9_weekly_metrics.py`、`tests/agent/test_compress_unified_caliber.py`、
      `tests/agent/test_compress_threshold_source.py`、`tests/scripts/test_b9_weekly_metrics.py`。
      修法 = **追加到行尾**，前缀与实参顺序一律不动。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import context_compressor as cpm  # noqa: E402

_LOGGER_NAME = "agent.context_compressor"


class _Capture(logging.Handler):
    """收成品串——正是消费者（grep / 正则）看到的东西。"""

    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):  # noqa: A003
        self.lines.append(record.getMessage())


@pytest.fixture()
def captured():
    lg = logging.getLogger(_LOGGER_NAME)
    h = _Capture()
    lg.addHandler(h)
    old_level = lg.level
    lg.setLevel(logging.INFO)
    try:
        yield h
    finally:
        lg.removeHandler(h)
        lg.setLevel(old_level)


def _record(msg, args=None):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


# ── D2：前缀契约 ────────────────────────────────────────────────────────
def test_prefix_contract_preserved(captured):
    """`[COMPRESS] skip layer=agent ...` 必须仍是行的**开头**（4 个消费者靠它解析）。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] skip layer=agent tokens=%s threshold=%s", 1145754, 120000
    )
    assert len(captured.lines) == 1
    line = captured.lines[0]
    assert line.startswith("[COMPRESS] skip layer=agent tokens=1145754 threshold=120000"), line
    assert " pid=" in line and " run=" in line
    # 注入必须在**行尾**，不能插进前缀之后
    assert line.index("layer=agent") < line.index("pid=")


def test_result_line_anchor_preserved(captured):
    """b9 周报消费者的锚点是 `[COMPRESS] result layer=agent msgs=`——逐字不许动。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] result layer=agent msgs=%d->%d mode=%s", 215, 56, "llm"
    )
    line = captured.lines[0]
    assert "[COMPRESS] result layer=agent msgs=215->56 mode=llm" in line


# ── D1：不得因注入丢掉整行 ──────────────────────────────────────────────
def test_no_type_error_when_args_present(captured):
    """D1 复现点：多实参 + 多格式符，注入后 getMessage() 不得抛 TypeError。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] skip layer=agent tokens=%s threshold=%s reason=%s", 1, 2, "cfg"
    )
    assert len(captured.lines) == 1
    assert "tokens=1 threshold=2 reason=cfg" in captured.lines[0]


def test_filter_on_raw_record_does_not_corrupt_format(captured):
    """直接对 LogRecord 施加 filter（不经 logger）——最贴近线上 handler 链的形态。"""
    rec = _record("[COMPRESS] abort layer=agent reason=%s msgs=%s", ("no_api_key", "323/327"))
    f = cpm._CompressAttributionFilter()
    assert f.filter(rec) is True
    # 不得抛异常，且格式符与实参仍一一对应
    out = rec.getMessage()
    assert "reason=no_api_key msgs=323/327" in out
    assert "pid=" in out and "run=" in out


def test_missing_args_form_supported(captured):
    """args=None 的形态（纯字面量消息）也要能追加，且不产生多余实参。"""
    logging.getLogger(_LOGGER_NAME).info("[COMPRESS] something literal happened")
    line = captured.lines[0]
    assert line.startswith("[COMPRESS] something literal happened")
    assert "pid=" in line and "run=" in line


def test_dict_args_form_supported(captured):
    """dict 形态实参（%(name)s）不得被当成 tuple 追加而炸掉。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] ratio=%(rate)s layer=%(layer)s", {"rate": 0.45, "layer": "agent"}
    )
    line = captured.lines[0]
    assert "ratio=0.45 layer=agent" in line
    assert "pid=" in line and "run=" in line


# ── 幂等 / 不越界 ───────────────────────────────────────────────────────
def test_no_double_injection(captured):
    """已经带归属字段的行不得被再注入一次（否则会出现两个 pid=）。"""
    logging.getLogger(_LOGGER_NAME).info("[COMPRESS] skip layer=agent pid=1 run=abc")
    line = captured.lines[0]
    assert line.count("pid=") == 1
    assert line.count("run=") == 1


def test_non_compress_lines_untouched(captured):
    """非 [COMPRESS] 行一个字节都不动（例如 [P2-1] 验证钩子日志）。"""
    logging.getLogger(_LOGGER_NAME).info("[P2-1] 实体保留率 %.0f%% OK", 89.0)
    line = captured.lines[0]
    assert line.startswith("[P2-1] 实体保留率 89% OK")
    assert "pid=" not in line


def test_direct_filter_is_idempotent():
    """连续两次 filter 同一 record ⇒ 仍只有一个归属字段组。"""
    f = cpm._CompressAttributionFilter()
    rec = _record("[COMPRESS] skip layer=agent tokens=%s", (7,))
    f.filter(rec)
    f.filter(rec)
    out = rec.getMessage()
    assert out.count("pid=") == 1 and "tokens=7" in out


def test_filter_never_raises_on_exotic_msg():
    """非字符串 msg（陌生 logger 用法）必须 fail-open，绝不让日志因注入而丢。"""
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, object(), None, None)
    assert cpm._CompressAttributionFilter().filter(rec) is True


# ── 归属字段本身 ────────────────────────────────────────────────────────
def test_run_tag_returns_string():
    tag = cpm._run_tag()
    assert isinstance(tag, str) and tag != ""


def test_attribution_filter_installed_on_module_logger():
    """模块导入即接线（这是 T21 覆盖『全部现有与未来 [COMPRESS] 行』的机制）。"""
    lg = logging.getLogger(_LOGGER_NAME)
    assert any(isinstance(f, cpm._CompressAttributionFilter) for f in lg.filters)
