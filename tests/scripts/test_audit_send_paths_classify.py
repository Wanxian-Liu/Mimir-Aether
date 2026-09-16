"""C 组 C4 · audit_send_paths.py 分类器（量具自审：改量具必须带负控）。

背景：该脚本是 D7「发件路径归一」的**唯一可回归口径**。2026-09-16 C4 发现它把
「路径组件式」写法误判为违规（2 例假阳性）——修量具的规矩是**同时证明没被改松**：
  * 组件式 `.openclaw/data/buzz-inbox-x.jsonl` ⇒ canonical（修复目标）
  * 死路径 `~/.buzz-nostr/state/...` / `/tmp/...` / 相对路径 ⇒ **仍然 violation**（负控）
  * 纯文件名模板 ⇒ basename（目录由 canonical 常量决定，不算漂移）
  * 散文/长串/含换行 ⇒ None（不算路径用法）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import audit_send_paths as asp  # noqa: E402


@pytest.mark.parametrize(
    "value, expected",
    [
        # 组件式（本次修复的假阳性）
        (".openclaw/data/buzz-inbox-hermes.jsonl", "canonical"),
        # 绝对 / 家目录式（原本就正确）
        ("/home/rayliu/.openclaw/data/buzz-inbox-hermes.jsonl", "canonical"),
        ("~/.openclaw/data/buzz-inbox-hermes.jsonl", "canonical"),
        # 负控：死路径与漂移必须继续被判违规
        ("~/.buzz-nostr/state/buzz-inbox-hermes.jsonl", "violation"),
        ("/tmp/buzz-inbox-hermes.jsonl", "violation"),
        ("openclaw/data-typo/buzz-inbox-hermes.jsonl", "violation"),
        # 文件名模板
        ("buzz-inbox", "basename"),
        ("buzz-inbox-hermes.jsonl", "basename"),
        # 非路径用法
        ("不是路径的字符串", None),
    ],
)
def test_classify(value, expected):
    assert asp._classify(value) == expected


def test_classify_ignores_prose_and_multiline():
    prose = "我们在报文正文里提到 buzz-inbox-hermes.jsonl 这个文件名，" * 6
    assert asp._classify(prose) is None
    assert asp._classify("buzz-inbox-hermes.jsonl\n第二行") is None
