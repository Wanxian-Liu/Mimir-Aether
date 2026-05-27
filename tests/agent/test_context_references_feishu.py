"""HERM-CTX-02: Feishu natural-language URL references in context_references."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.context_references import (
    message_has_context_references,
    parse_context_references,
    parse_feishu_natural_references,
    preprocess_context_references,
)


def test_parse_feishu_natural_docx_url():
    msg = "请看一下飞书文档 https://acme.feishu.cn/docx/AbCdEfGhIjKlMnOp 里的方案"
    refs = parse_feishu_natural_references(msg)
    assert len(refs) == 1
    assert refs[0].kind == "feishu"
    assert "feishu.cn/docx/AbCdEfGhIjKlMnOp" in refs[0].target


def test_parse_feishu_larksuite_wiki_url():
    msg = "See https://team.larksuite.com/wiki/TOKEN123 for context"
    refs = parse_feishu_natural_references(msg)
    assert len(refs) == 1
    assert refs[0].kind == "feishu"


def test_parse_context_references_merges_at_and_feishu():
    msg = "@file:README.md and https://x.feishu.cn/docx/DocToken123"
    refs = parse_context_references(msg)
    kinds = {r.kind for r in refs}
    assert "file" in kinds
    assert "feishu" in kinds


def test_explicit_at_url_feishu_not_duplicated():
    msg = "@url:https://x.feishu.cn/docx/DupToken"
    refs = parse_context_references(msg)
    feishu = [r for r in refs if r.kind == "feishu"]
    url = [r for r in refs if r.kind == "url"]
    assert len(feishu) == 0
    assert len(url) == 1


def test_message_has_context_references_without_at():
    msg = "飞书链接 https://x.feishu.cn/wiki/WikiToken"
    assert "@" not in msg
    assert message_has_context_references(msg) is True


def test_preprocess_feishu_injects_stub_block(tmp_path: Path):
    msg = "总结这个 https://demo.feishu.cn/docx/SummaryDocToken"
    result = preprocess_context_references(msg, cwd=tmp_path)
    assert result.expanded is True
    assert any(r.kind == "feishu" for r in result.references)
    assert "Feishu document link" in result.message
    assert "SummaryDocToken" in result.message
