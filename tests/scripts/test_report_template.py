"""A2 · 报告模板「未替换占位符」闸（格式符字面量 bug 第 3 次复发）。

背景：报告行用 `%` 格式化写，**漏传参数时 Python 不报错** —— 字面 `%s` 静默落盘。
复发两次修不掉，是因为每个探针脚本都自带一份 `log()`，修的是「那一行」而不是
「那一类」。本测试锁的是机制：`scripts/report_template.py` 是唯一漏斗，未替换
占位符 ⇒ 当场报错；`Report.write()` 是落盘前的终检闸。

第 1 例是**复发点原文**（`~/.mimiraether/logs/n13_restart_window.log` 第 41 行）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import report_template as rt  # noqa: E402


# ── 复发点：N13 §6 原文 ──────────────────────────────────────────────────────

N13_LINE6_LITERAL = (
    "- 告警**真的发到了 home 频道**（`%s`）⇒ 刘哥飞书应收到一条「⚠ 投递失败告警」"
)


def test_regression_n13_line6_literal_placeholder_now_raises():
    """正控：带 `%s` 且漏传参数的模板 ⇒ 必须报错，绝不允许静默落盘。"""
    with pytest.raises(rt.UnrenderedTemplateError) as ei:
        rt.render(N13_LINE6_LITERAL)
    assert "%s" in str(ei.value)


def test_regression_same_line_renders_when_arg_supplied():
    """补参数后正常渲染，结果里不得再有 `%s`。"""
    out = rt.render("- 告警真的发到了 home 频道（`%s`）", "oc_8af3")
    assert "oc_8af3" in out
    assert "%s" not in out


# ── 负控：散文里的百分号不得被误判 ───────────────────────────────────────────

@pytest.mark.parametrize(
    "prose",
    [
        "命中 92.5% 完成",
        "占比 50% and counting",
        "89% of the samples",
        "压缩率 11.7%~17.5%",
        "Cache 命中 92.5%（加权）",
    ],
)
def test_prose_percent_not_false_positive(prose):
    assert rt.render(prose) == prose


def test_literal_percent_escape_convention():
    """约定：字面百分号写 `%%`，渲染后还原为单个 `%`。"""
    assert rt.render("完成度 100%%") == "完成度 100%"


# ── 有参数通路 ───────────────────────────────────────────────────────────────

def test_render_with_args_and_positional():
    assert rt.render("- PID `%s` · 启动 `%s`", "384724", "Fri") == "- PID `384724` · 启动 `Fri`"
    assert rt.render("命中 **%d** 行", 2) == "命中 **2** 行"


def test_render_named_kwargs():
    assert rt.render("%(chat)s 收到告警", chat="oc_1") == "oc_1 收到告警"


def test_render_named_without_kwargs_raises():
    with pytest.raises(rt.UnrenderedTemplateError):
        rt.render("%(chat)s 收到告警")


def test_missing_args_wrapped_as_domain_error():
    with pytest.raises(rt.UnrenderedTemplateError) as ei:
        rt.render("%s %s", "only-one")
    assert "模板渲染失败" in str(ei.value)


def test_n3_crash_form_is_wrapped_not_naked_valueerror():
    """N3 复发形态：字面 `%（` 又施加 `%` 运算 ⇒ 原先裸 ValueError 崩，现为可读异常。"""
    with pytest.raises(rt.UnrenderedTemplateError) as ei:
        rt.render("（%（ 上报）", "x")
    assert "模板渲染失败" in str(ei.value)
    assert "%（" in str(ei.value)


def test_non_str_template_rejected():
    with pytest.raises(rt.UnrenderedTemplateError):
        rt.render(None)  # type: ignore[arg-type]


# ── 整篇终检 ─────────────────────────────────────────────────────────────────

def test_scan_catches_leak():
    hits = rt.scan_placeholders("正常行\n- 频道（`%s`）\n- 计数 %d\n")
    assert len(hits) == 2


def test_scan_skips_fenced_blocks():
    """围栏内是外部捕获文本 ⇒ 终检不误伤（raw() 走这条豁免）。"""
    assert rt.scan_placeholders("正常行\n```\nraw %s payload\n```\n") == []


# ── 落盘闸（终检） ───────────────────────────────────────────────────────────

def test_write_is_terminal_gate_and_leaves_no_partial_file(tmp_path):
    """即使某行绕开 `line()`，`write()` 仍拦住，且**不产出半成品文件**。"""
    rep = rt.Report()
    rep.line("# 标题")
    rep.extend(["- 频道（`%s`）"])  # 绕过 render 的路径
    target = tmp_path / "should_not_exist.md"
    with pytest.raises(rt.UnrenderedTemplateError):
        rep.write(target)
    assert not target.exists()


def test_write_ok_and_content_on_disk(tmp_path):
    rep = rt.Report()
    rep.line("# N13 报告")
    rep.line("- PID `%s`", "384724")
    rep.raw("external %s output")  # 显式豁免
    p = rep.write(tmp_path / "ok.md")
    text = p.read_text(encoding="utf-8")
    assert p.exists()
    assert "384724" in text
    assert "external %s output" in text


def test_emit_checks_before_printing(capsys):
    rep = rt.Report()
    rep.extend(["- 频道（`%s`）"])
    with pytest.raises(rt.UnrenderedTemplateError):
        rep.emit()
    assert capsys.readouterr().out == ""


# ── 设计自证：参数值里天然含 `%s` 不得被误判 ───────────────────────────────────

def test_arg_value_containing_placeholder_is_not_a_leak():
    """受控双探针发现的假阳性：参数**值**里含 `%s`（如外部错误文本）不是泄漏。

    第一版实现有「渲染后残留复检」兜底，本例会误报 ⇒ 已删。这是该删除的回归锁。
    """
    out = rt.render("- 失败：%s", "upstream said: %s missing")
    assert out == "- 失败：upstream said: %s missing"


def test_over_supplied_args_raise():
    with pytest.raises(rt.UnrenderedTemplateError):
        rt.render("此行没有占位符", "多余参数")
