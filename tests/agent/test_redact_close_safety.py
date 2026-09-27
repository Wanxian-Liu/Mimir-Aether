"""日志脱敏的关闭期安全（2026-09-28）用例。

背景：``RedactingFormatter.format()`` → ``redact_sensitive_text()`` 内**惰性**
``from agent.redact_rules import apply_loaded_rules``。解释器关闭期
``sys.meta_path is None`` ⇒ ImportError ⇒ logging emit 二次失败 ⇒ 级联
Traceback（实测 gateway.log 23 条）。本文件钉住两条性质：
① 该函数体内不再有 import 语句；② 格式化器 fail-closed（不放行未脱敏原文）。
"""
import inspect
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import agent.redact as rd

SECRET = "sk-abcdefghij1234567890"


def test_no_lazy_import_inside_redact_sensitive_text():
    """结构闸：函数体内出现 import ⇒ 关闭期仍会炸（回归即红）。"""
    src = inspect.getsource(rd.redact_sensitive_text)
    assert "import" not in src, "应改为模块导入期解析，禁止函数内惰性 import"


def test_rules_resolved_at_import_time():
    assert rd._apply_loaded_rules is not None


def test_formatter_withholds_when_redaction_fails(monkeypatch):
    """fail-closed：脱敏失败时**不得**返回原文（否则未脱敏内容落盘）。"""

    def _boom(_text):
        raise RuntimeError("sys.meta_path is None")

    monkeypatch.setattr(rd, "redact_sensitive_text", _boom)
    rec = logging.LogRecord("n", logging.WARNING, __file__, 1, "leak " + SECRET, None, None)
    out = rd.RedactingFormatter("%(message)s").format(rec)
    assert out == "[REDACTION FAILED - message withheld]"
    assert SECRET not in out


def test_formatter_redacts_normally():
    """正控：正常路径仍真脱敏。"""
    rec = logging.LogRecord("n", logging.WARNING, __file__, 1, "key " + SECRET + " end", None, None)
    out = rd.RedactingFormatter("%(message)s").format(rec)
    assert SECRET not in out and "key" in out
