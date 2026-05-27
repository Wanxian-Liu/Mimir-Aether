"""Horizon C Wave 12 · HERM-CTX-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CTX_REF = ROOT / "agent" / "context_references.py"
CORE_LOOP = ROOT / "agent" / "core_loop.py"
INBOUND = ROOT / "gateway" / "router" / "inbound_prep_mixin.py"
SMOKE = ROOT / "data" / "feishu_context_smoke.json"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "herm-ctx-02-closeout.md"


def test_herm_ctx_02_feishu_parser():
    text = CTX_REF.read_text(encoding="utf-8")
    for symbol in (
        "parse_feishu_natural_references",
        "message_has_context_references",
        "FEISHU_URL_PATTERN",
        "_expand_feishu_reference",
    ):
        assert symbol in text


def test_herm_ctx_02_gateway_and_core_trigger():
    core = CORE_LOOP.read_text(encoding="utf-8")
    inbound = INBOUND.read_text(encoding="utf-8")
    assert "message_has_context_references" in core
    assert "message_has_context_references" in inbound


def test_herm_ctx_02_smoke_fixture():
    assert SMOKE.is_file()
    assert "feishu.cn/docx" in SMOKE.read_text(encoding="utf-8")


def test_herm_ctx_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_context_references_feishu.py" in tier0
    assert "test_horizon_herm_ctx_02.py" in tier0


def test_herm_ctx_02_closeout_exists():
    assert CLOSEOUT.is_file()
