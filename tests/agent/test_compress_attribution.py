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


# ══════════════════════════════════════════════════════════════════════════
# 批1 附条件（2026-09-15 四方会议裁决 #1 · Mimir 收尾）
#   护栏 1：跨行 msg（msg 含 \n）—— 归属字段必须仍落在**锚点行**上
#   护栏 4：logger 覆盖 —— 明示 coverage = 1 logger + 传播行为受控差分断言
# ══════════════════════════════════════════════════════════════════════════

# ── 护栏 1：跨行 msg（RED 于修复前：pid= 落在第 2 物理行 ⇒ 锚点行内命中 0）──
def test_multiline_tuple_args_attribution_on_anchor_line(captured):
    """msg 内含真换行 ⇒ 归属字段必须在**含 [COMPRESS] 的那一行**（消费者只看第 1 行）。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] abort layer=agent reason=%s\npayload=second-line", "no_api_key"
    )
    assert len(captured.lines) == 1
    line = captured.lines[0]
    head, _, tail = line.partition("\n")
    assert head.startswith("[COMPRESS] abort layer=agent reason=no_api_key"), line
    assert " pid=" in head and " run=" in head, line          # ← 修复前在此断言失败
    assert line.count("pid=") == 1 and line.count("run=") == 1
    assert tail == "payload=second-line"                      # 正文一字节不动


def test_multiline_literal_attribution_on_anchor_line(captured):
    """args=None 的跨行 msg 同样必须落在锚点行。"""
    logging.getLogger(_LOGGER_NAME).info("[COMPRESS] multiline literal\nbody=kept")
    line = captured.lines[0]
    head = line.split("\n", 1)[0]
    assert head.startswith("[COMPRESS] multiline literal") and "pid=" in head
    assert line.split("\n", 1)[1] == "body=kept"


def test_multiline_dict_args_attribution_on_anchor_line(captured):
    """dict 形态实参 + 跨行 ⇒ 也不能把字段挤到第二行。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] ratio=%(rate)s layer=%(layer)s\nrest=1", {"rate": 0.45, "layer": "agent"}
    )
    line = captured.lines[0]
    head = line.split("\n", 1)[0]
    assert "ratio=0.45 layer=agent" in head
    assert "pid=" in head and head.count("pid=") == 1
    assert line.endswith("rest=1")


def test_multiline_several_newlines_only_first_line_carries_attribution(captured):
    """多行（≥2 个换行）⇒ 只在第 1 行追加一次，其余行不注入。"""
    logging.getLogger(_LOGGER_NAME).info("[COMPRESS] start\nmid\nend")
    line = captured.lines[0]
    parts = line.split("\n")
    assert len(parts) == 3
    assert "pid=" in parts[0]
    assert "pid=" not in parts[1] and "pid=" not in parts[2]


def test_inject_single_line_is_plain_append():
    """单行等价性（回归钉）：旧行为 = 拼在末尾，逐字节不许变。"""
    f = cpm._CompressAttributionFilter()
    assert f._inject("[COMPRESS] x=1", " pid=7 run=r") == "[COMPRESS] x=1 pid=7 run=r"
    assert f._inject("[COMPRESS] a\nb", " pid=7 run=r") == "[COMPRESS] a pid=7 run=r\nb"


def test_multiline_does_not_break_prefix_contract(captured):
    """跨行场景下 D2 前缀契约仍成立：`[COMPRESS] skip layer=agent tokens=` 逐字在行首。"""
    logging.getLogger(_LOGGER_NAME).info(
        "[COMPRESS] skip layer=agent tokens=%s threshold=%s\nnote=still-here", 9, 3
    )
    head = captured.lines[0].split("\n", 1)[0]
    assert head.startswith("[COMPRESS] skip layer=agent tokens=9 threshold=3")


# ── 护栏 4：coverage = 1 logger 明示 + 传播受控差分 ───────────────────────
_SIBLING = "agent.compress_cooldown"          # 真实兄弟 logger（D10 的现场）


class _RecordCapture(logging.Handler):
    """收 **record**（延迟取 getMessage）——传播链上的注入发生在下游 handler，早取会看不到。"""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):  # noqa: A003
        self.records.append(record)


def _capture_records(name):
    lg = logging.getLogger(name)
    h = _RecordCapture()
    lg.addHandler(h)
    lg.setLevel(logging.INFO)
    return lg, h


def test_coverage_declared_as_single_logger():
    """**明示**：覆盖口径只声明 1 个 logger，不得写成「全覆盖」。"""
    assert cpm.ATTRIBUTION_COVERED_LOGGERS == (_LOGGER_NAME,)
    lg = logging.getLogger(_LOGGER_NAME)
    assert any(isinstance(f, cpm._CompressAttributionFilter) for f in lg.filters)
    assert not any(isinstance(f, cpm._CompressAttributionFilter) for f in logging.getLogger(_SIBLING).filters)


def test_coverage_single_logger_sibling_records_not_injected():
    """受控差分 ㈠（反例/控制组）：兄弟 logger 的 [COMPRESS] 行**不被注入**。

    这是 D10 未解决的根因——本 filter 只挂在 `agent.context_compressor` 上，
    兄弟 logger 的记录 propagate 时只经过祖先的 **handler**，不经过祖先 logger 的 **filter**。
    """
    lg, cap = _capture_records(_SIBLING)
    old_prop = lg.propagate
    try:
        lg.info("[COMPRESS] cooldown armed failures=%d", 3)
    finally:
        lg.removeHandler(cap)
        lg.propagate = old_prop
    assert len(cap.records) == 1
    msg = cap.records[0].getMessage()
    assert msg.startswith("[COMPRESS] cooldown armed failures=3")
    assert "pid=" not in msg and "run=" not in msg     # ← 未被覆盖（1 logger 口径的事实）


def test_ancestor_handler_filter_covers_sibling():
    """受控差分 ㈢（处置组）：filter 挂**祖先 handler** ⇒ 兄弟 logger 也被注入。"""
    ancestor = logging.getLogger("agent")
    carrier = cpm.install_attribution_on_ancestor_handler("agent")
    lg_sib, cap_sib = _capture_records(_SIBLING)
    lg_mod = logging.getLogger(_LOGGER_NAME)
    cap_mod = _RecordCapture()
    lg_mod.addHandler(cap_mod)
    _old_lvl = lg_mod.level
    lg_mod.setLevel(logging.INFO)          # root 默认 WARNING ⇒ 不置 INFO 该记录会被直接丢弃
    try:
        lg_sib.info("[COMPRESS] cooldown armed failures=%d delay=600s", 3)
        lg_mod.info("[COMPRESS] skip layer=agent tokens=%d", 1)
    finally:
        lg_sib.removeHandler(cap_sib)
        lg_mod.removeHandler(cap_mod)
        lg_mod.setLevel(_old_lvl)
        ancestor.removeHandler(carrier)

    sib = cap_sib.records[0].getMessage()
    mod = cap_mod.records[0].getMessage()
    assert "pid=" in sib and "run=" in sib            # 兄弟 logger 被覆盖
    assert sib.count("pid=") == 1                     # 且只注入一次
    assert mod.startswith("[COMPRESS] skip layer=agent tokens=1")
    assert mod.count("pid=") == 1                     # 双重过滤不产生双份字段


def test_ancestor_carrier_install_is_idempotent():
    """幂等：重复安装返回同一个载体 handler，不叠加。"""
    ancestor = logging.getLogger("agent")
    h1 = cpm.install_attribution_on_ancestor_handler("agent")
    h2 = cpm.install_attribution_on_ancestor_handler("agent")
    try:
        assert h1 is h2
        assert sum(isinstance(x, cpm._AttributionCarrierHandler) for x in ancestor.handlers) == 1
    finally:
        ancestor.removeHandler(h1)


def test_carrier_handler_emits_nothing(captured):
    """载体 handler 本身不得输出日志（它不是输出端，只是 filter 载体）。"""
    ancestor = logging.getLogger("agent")
    carrier = cpm.install_attribution_on_ancestor_handler("agent")
    try:
        logging.getLogger(_LOGGER_NAME).info("[COMPRESS] probe carrier")
        logging.getLogger(_LOGGER_NAME).info("plain non-compress line")
    finally:
        ancestor.removeHandler(carrier)
    assert captured.lines[0].startswith("[COMPRESS] probe carrier")
    assert "plain non-compress line" in captured.lines[1]
    assert "pid=" not in captured.lines[1]
