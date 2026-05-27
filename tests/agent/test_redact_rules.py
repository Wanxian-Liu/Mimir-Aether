"""HERM-RED-02: ops-editable redact_rules.json loading and application."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import redact as redact_mod
from agent.redact_rules import (
    RedactRulesConfig,
    apply_configurable_redaction,
    load_redact_rules,
    reset_redact_rules_cache,
    resolve_redact_rules_path,
)


@pytest.fixture(autouse=True)
def _clear_rules_cache() -> None:
    reset_redact_rules_cache()
    yield
    reset_redact_rules_cache()


def _write_rules(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_prefers_explicit_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_file = tmp_path / "custom.json"
    rules_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MIMIR_REDACT_RULES", str(rules_file))
    assert resolve_redact_rules_path() == rules_file


def test_load_valid_rules_compiles_patterns(tmp_path: Path) -> None:
    rules_file = tmp_path / "redact_rules.json"
    _write_rules(
        rules_file,
        {
            "version": 1,
            "regex_patterns": [{"id": "acme", "pattern": r"acme_[A-Za-z0-9]{8,}"}],
            "query_param_names": ["apikey"],
            "json_field_names": ["client_secret"],
        },
    )
    cfg = load_redact_rules(rules_file)
    assert isinstance(cfg, RedactRulesConfig)
    assert len(cfg.regex_patterns) == 1
    assert len(cfg.query_param_res) == 1
    assert len(cfg.json_field_res) == 1


def test_apply_custom_regex_and_query_param(tmp_path: Path) -> None:
    rules_file = tmp_path / "rules.json"
    _write_rules(
        rules_file,
        {
            "regex_patterns": [{"pattern": r"acme_[A-Za-z0-9]{8,}"}],
            "query_param_names": ["apikey"],
        },
    )
    cfg = load_redact_rules(rules_file)
    text = "token acme_deadbeef1234 in https://x.com?apikey=supersecretvalue"
    out = apply_configurable_redaction(text, cfg)
    assert "acme_deadbeef1234" not in out
    assert "supersecretvalue" not in out
    assert "acme_" in out or "***" in out


def test_bad_json_returns_empty_rules(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    cfg = load_redact_rules(bad)
    assert cfg.regex_patterns == []
    assert cfg.query_param_res == []
    assert apply_configurable_redaction("acme_abcdefghij", cfg) == "acme_abcdefghij"


def test_empty_rules_no_op(tmp_path: Path) -> None:
    rules_file = tmp_path / "empty.json"
    _write_rules(rules_file, {})
    cfg = load_redact_rules(rules_file)
    assert apply_configurable_redaction("plain text", cfg) == "plain text"


def test_invalid_regex_entry_skipped(tmp_path: Path) -> None:
    rules_file = tmp_path / "rules.json"
    _write_rules(
        rules_file,
        {
            "regex_patterns": [
                {"pattern": "("},
                {"pattern": r"oktag_[A-Za-z0-9]{4,}"},
            ],
        },
    )
    cfg = load_redact_rules(rules_file)
    assert len(cfg.regex_patterns) == 1
    out = apply_configurable_redaction("oktag_abcd1234", cfg)
    assert "oktag_abcd1234" not in out


def test_redact_sensitive_text_uses_loaded_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rules_file = tmp_path / "redact_rules.json"
    _write_rules(
        rules_file,
        {"regex_patterns": [{"pattern": r"customsecret_[A-Za-z0-9]{6,}"}]},
    )
    monkeypatch.setenv("MIMIR_REDACT_RULES", str(rules_file))
    monkeypatch.setenv("HERMES_REDACT_SECRETS", "true")
    reset_redact_rules_cache()
    text = "leak customsecret_abcdefgh end"
    out = redact_mod.redact_sensitive_text(text)
    assert "customsecret_abcdefgh" not in out


def test_builtin_prefix_still_redacts_with_extra_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rules_file = tmp_path / "redact_rules.json"
    _write_rules(rules_file, {"regex_patterns": []})
    monkeypatch.setenv("MIMIR_REDACT_RULES", str(rules_file))
    monkeypatch.setenv("HERMES_REDACT_SECRETS", "true")
    reset_redact_rules_cache()
    key = "sk-" + "a" * 20
    out = redact_mod.redact_sensitive_text(f"key={key}")
    assert key not in out
