"""Guardrails for tier0 synthetic session IDs."""

from __future__ import annotations

from pathlib import Path

from agent.synthetic_sessions import (
    evolution_allowed_for_session,
    is_default_mimir_home,
    is_synthetic_session_id,
)


def test_is_synthetic_session_id():
    assert is_synthetic_session_id("iq07-sess")
    assert is_synthetic_session_id("iq40-sess")
    assert is_synthetic_session_id("fb-sess")
    assert is_synthetic_session_id("iqevo-abc")
    assert not is_synthetic_session_id("550e8400-e29b-41d4-a716-446655440000")


def test_evolution_blocked_on_production_home(monkeypatch):
    prod = Path.home() / ".mimiraether"
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(prod))
    monkeypatch.setenv("HERMES_HOME", str(prod))
    assert is_default_mimir_home()
    assert not evolution_allowed_for_session("iq07-sess")
    assert evolution_allowed_for_session("real-session-id")


def test_evolution_allowed_on_tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert evolution_allowed_for_session("iq07-sess")
    assert not is_default_mimir_home(tmp_path)
