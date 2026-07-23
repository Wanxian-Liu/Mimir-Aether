"""Tests for verify_before_report_guard — pure functions only."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add repo root so we can import the guard as a module
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.verify_before_report_guard import (
    CLAIM_PATTERNS,
    VERIFICATION_TOOL_PATTERNS,
    has_claim,
    has_verification_call,
    check_verification,
)


# ═══════════════════════════════════════════════════════════════════════════
# has_claim
# ═══════════════════════════════════════════════════════════════════════════

def test_has_claim_chinese_done() -> None:
    assert has_claim("已完成") is True
    assert has_claim("已修") is True
    assert has_claim("已修复") is True
    assert has_claim("已验证") is True
    assert has_claim("验证通过") is True


def test_has_claim_english_done() -> None:
    assert has_claim("done") is True
    assert has_claim("this is finished") is True
    assert has_claim("I fixed the bug") is True
    assert has_claim("verified") is True


def test_has_claim_no_claim() -> None:
    assert has_claim("正在读盘确认数据") is False
    assert has_claim("让我跑一下测试") is False
    assert has_claim("我在检查结果") is False
    assert has_claim("") is False
    assert has_claim(None) is False  # type: ignore[arg-type]


def test_has_claim_edge_success() -> None:
    """'成功' alone triggers; '成功了吗' as question should NOT trigger (no pattern match)."""
    assert has_claim("成功了") is True
    # "成功" without 了/地/完成 can still match via \b成功\b(?:了|地|完成|提交)
    # So "成功了吗" won't match since after '成功' there's '了吗' which isn't in the group
    assert has_claim("成功了吗") is False
    assert has_claim("成功了吗？") is False


def test_has_claim_success_no_suffix() -> None:
    """Bare word '成功' alone (no suffix) should NOT trigger."""
    assert has_claim("成功") is False


def test_has_claim_mixed_text() -> None:
    """'已完成' as part of longer word '已完成验证' should NOT trigger (no word boundary)."""
    long_text = "让我先读一下文件。已完成验证，盘上数据确认无误。"
    assert has_claim(long_text) is False

def test_has_claim_standalone_chi_done() -> None:
    """Standalone '已完成' (followed by punctuation/newline) MUST trigger."""
    texts = [
        "文件已读取。已完成。",
        "已完成\n所有步骤已通过。",
        "检查完毕，已完成！",
    ]
    for t in texts:
        assert has_claim(t) is True, f"Failed on: {t!r}"


# ═══════════════════════════════════════════════════════════════════════════
# has_verification_call
# ═══════════════════════════════════════════════════════════════════════════

def test_has_verification_with_read_file() -> None:
    calls = [{"tool": "read_file", "path": "data/persistent.json"}]
    assert has_verification_call(calls) is True


def test_has_verification_with_json_load() -> None:
    calls = [{"tool": "execute_code", "code": "json.load(open('data/x.json'))"}]
    assert has_verification_call(calls) is True


def test_has_verification_with_terminal_cat() -> None:
    calls = [{"tool": "terminal", "command": "cat data/persistent.json"}]
    assert has_verification_call(calls) is True


def test_has_verification_empty_history() -> None:
    assert has_verification_call([]) is False
    assert has_verification_call(None) is False  # type: ignore[arg-type]


def test_has_verification_only_write_not_counted() -> None:
    """write_file / patch are NOT verification."""
    calls = [{"tool": "write_file", "path": "test.py"}]
    assert has_verification_call(calls) is False


def test_has_verification_recent_only() -> None:
    """Only last N calls matter (default lookback=5)."""
    old = [{"tool": "read_file", "path": "data/persistent.json"}]
    recent = [{"tool": "write_file", "path": "test.py"}] * 5
    assert has_verification_call(old + recent, lookback=5) is False
    assert has_verification_call(old + recent, lookback=10) is True


# ═══════════════════════════════════════════════════════════════════════════
# check_verification  (integration of has_claim + has_verification_call)
# ═══════════════════════════════════════════════════════════════════════════

def test_check_verified_pass() -> None:
    result = check_verification("已完成", [{"tool": "read_file"}])
    assert result["blocked"] is False
    assert result["reason"] == "verified"


def test_check_claim_no_verification_blocked() -> None:
    result = check_verification("已完成", [{"tool": "write_file"}])
    assert result["blocked"] is True
    assert result["reason"] == "claim_without_verification"


def test_check_no_claim_no_block() -> None:
    result = check_verification("正在运行测试", [{"tool": "write_file"}])
    assert result["blocked"] is False
    assert result["reason"] == "no_claim"


def test_check_env_disabled() -> None:
    import os
    old = os.environ.get("MIMIR_VERIFY_BEFORE_REPORT")
    os.environ["MIMIR_VERIFY_BEFORE_REPORT"] = "0"
    result = check_verification("已完成", [{"tool": "write_file"}])
    assert result["blocked"] is False
    assert result["reason"] == "env_gate_disabled"
    if old is None:
        del os.environ["MIMIR_VERIFY_BEFORE_REPORT"]
    else:
        os.environ["MIMIR_VERIFY_BEFORE_REPORT"] = old
