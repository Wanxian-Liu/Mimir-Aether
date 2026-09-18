"""N10 (2026-09-18) -- disagreeing home-channel sources must be AUDIBLE.

Chain of incidents this closes:

  N8  a bare `deliver: "feishu"` failed on EVERY run, silently
      (`last_status="ok"`, 0 messages, 3 executions) because "None means use
      home channel" was documented but never implemented.
  N9  the fix was still too narrow: real adapters *return*
      `SendResult(success=False)` instead of raising, so a failure could hide
      one layer deeper. Production probe: job `44ff4165be31` -> Feishu
      `code=230001 invalid receive_id` -> job still `ok`.
  N10 "explicit chat_id is a stopgap" (Loki, `loki-n8-acceptance`, 補強 #2).
      Once a bare platform target resolves through the home channel, a **stale**
      key is worse than a missing one: the message is delivered to the WRONG
      chat while every status field still says success. `home_channel_chat_id`
      can be fed by three independent places
      (`gateway_config` / `env` / `config_yaml`) and nothing compared them.

What is asserted here:
  * two sources disagreeing => a conflict, logged at ERROR
  * one source, or none => NOT a conflict (negative control: a guard that
    fires on "not configured" trains everyone to ignore it)
  * precedence (gateway_config > env > config_yaml) is unchanged -- the
    resolver now delegates to the source map the guard audits, and this pins
    that refactor
  * the guard can never take the gateway down
"""
from __future__ import annotations

import logging
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import gateway.delivery as delivery_mod  # noqa: E402
from gateway.config import Platform  # noqa: E402
from gateway.delivery import DeliveryRouter  # noqa: E402


class StubConfig:
    """Minimal GatewayConfig stand-in (same shape N8/N9 tests use)."""

    def __init__(self, chat_id=None, boom=False):
        self._chat_id = chat_id
        self._boom = boom

    def get_home_channel(self, platform):
        if self._boom:
            raise RuntimeError("config exploded")
        if self._chat_id is None:
            return None
        return type("HC", (), {"chat_id": self._chat_id})()


def _home(monkeypatch, tmp_path, yaml_value=None, env_value=None, config_value=None):
    """Set up the three sources explicitly; unset ones stay absent."""
    monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    if yaml_value is not None:
        (tmp_path / "config.yaml").write_text(
            f"FEISHU_HOME_CHANNEL: {yaml_value}\n", encoding="utf-8"
        )
    if env_value is not None:
        monkeypatch.setenv("FEISHU_HOME_CHANNEL", env_value)
    return DeliveryRouter(config=StubConfig(config_value), adapters={})


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)


# --------------------------------------------------- conflict is reported
def test_disagreeing_sources_are_a_conflict(monkeypatch, tmp_path):
    r = _home(monkeypatch, tmp_path, yaml_value="oc_stale", config_value="oc_live")
    conflicts = r.check_home_channels([Platform.FEISHU])
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["platform"] == "feishu"
    assert c["effective"] == "oc_live"
    assert c["effective_source"] == "gateway_config"
    assert c["sources"] == {"gateway_config": "oc_live", "config_yaml": "oc_stale"}


def test_env_vs_yaml_conflict_is_detected(monkeypatch, tmp_path):
    r = _home(monkeypatch, tmp_path, yaml_value="oc_yaml", env_value="oc_env")
    conflicts = r.check_home_channels([Platform.FEISHU])
    assert len(conflicts) == 1
    assert conflicts[0]["effective_source"] == "env"


def test_conflict_is_logged_as_error(monkeypatch, tmp_path, caplog):
    r = _home(monkeypatch, tmp_path, yaml_value="oc_stale", config_value="oc_live")
    with caplog.at_level(logging.ERROR, logger="gateway.delivery"):
        found = r.log_home_channel_status([Platform.FEISHU])
    assert len(found) == 1
    msgs = [rec.getMessage() for rec in caplog.records]
    assert any("HOME CHANNEL CONFLICT" in m for m in msgs), msgs
    # the message must name the target it would actually send to
    assert any("oc_live" in m for m in msgs), msgs


# ------------------------------- negative controls: no conflict, no alarm
def test_agreeing_sources_are_not_a_conflict(monkeypatch, tmp_path):
    r = _home(monkeypatch, tmp_path, yaml_value="oc_same", config_value="oc_same")
    assert r.check_home_channels([Platform.FEISHU]) == []


def test_single_source_is_not_a_conflict(monkeypatch, tmp_path):
    """One source is normal operation -- not something to alarm about."""
    r = _home(monkeypatch, tmp_path, yaml_value="oc_only")
    assert r.check_home_channels([Platform.FEISHU]) == []


def test_no_source_is_not_a_conflict(monkeypatch, tmp_path):
    r = _home(monkeypatch, tmp_path)
    assert r.check_home_channels([Platform.FEISHU]) == []


def test_clean_configuration_logs_no_error(monkeypatch, tmp_path, caplog):
    """Clean config => no ERROR. (It still emits a "guard ran" INFO marker.)"""
    r = _home(monkeypatch, tmp_path, yaml_value="oc_only")
    with caplog.at_level(logging.ERROR, logger="gateway.delivery"):
        assert r.log_home_channel_status([Platform.FEISHU]) == []
    assert [rec.getMessage() for rec in caplog.records] == []


def test_guard_always_emits_a_ran_marker(monkeypatch, tmp_path, caplog):
    """The negative case must be falsifiable.

    "0 conflicts" and "the guard never ran" otherwise look identical in the log
    -- the same ambiguity N8/N9/N10 all fight. This INFO line is what makes
    "clean" distinguishable from "not executed".
    """
    r = _home(monkeypatch, tmp_path, yaml_value="oc_only")
    with caplog.at_level(logging.INFO, logger="gateway.delivery"):
        r.log_home_channel_status([Platform.FEISHU])
    infos = [rec.getMessage() for rec in caplog.records if rec.levelno == logging.INFO]
    assert any("Home channel check" in m for m in infos), infos


def test_ran_marker_counts_the_conflict(monkeypatch, tmp_path, caplog):
    r = _home(monkeypatch, tmp_path, yaml_value="oc_stale", config_value="oc_live")
    with caplog.at_level(logging.INFO, logger="gateway.delivery"):
        r.log_home_channel_status([Platform.FEISHU])
    infos = [rec.getMessage() for rec in caplog.records if rec.levelno == logging.INFO]
    assert any("1 conflict" in m for m in infos), infos


# --------------------------------------- precedence pinned (N8 regression)
def test_precedence_config_over_env_over_yaml(monkeypatch, tmp_path):
    r = _home(
        monkeypatch, tmp_path,
        yaml_value="oc_yaml", env_value="oc_env", config_value="oc_cfg",
    )
    assert r.home_channel_chat_id(Platform.FEISHU) == "oc_cfg"
    assert r.home_channel_resolution(Platform.FEISHU) == ("oc_cfg", "gateway_config")


def test_precedence_env_over_yaml_when_config_silent(monkeypatch, tmp_path):
    r = _home(monkeypatch, tmp_path, yaml_value="oc_yaml", env_value="oc_env")
    assert r.home_channel_resolution(Platform.FEISHU) == ("oc_env", "env")


def test_no_source_resolves_to_none(monkeypatch, tmp_path):
    r = _home(monkeypatch, tmp_path)
    assert r.home_channel_resolution(Platform.FEISHU) == (None, None)


# ------------------------------------------------------ guard robustness
def test_broken_config_does_not_raise(monkeypatch, tmp_path):
    """A config that explodes => that source is simply absent."""
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    r = DeliveryRouter(config=StubConfig(boom=True), adapters={})
    assert r.check_home_channels([Platform.FEISHU]) == []


def test_guard_never_raises_even_if_check_explodes(monkeypatch, tmp_path, caplog):
    r = _home(monkeypatch, tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("check exploded")

    monkeypatch.setattr(r, "check_home_channels", _boom)
    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        assert r.log_home_channel_status([Platform.FEISHU]) == []
    assert any("failed to run" in rec.getMessage() for rec in caplog.records)


def test_local_platform_is_skipped(monkeypatch, tmp_path):
    """Scanning every platform must work and must never report LOCAL."""
    r = _home(monkeypatch, tmp_path)
    assert all(c["platform"] != "local" for c in r.check_home_channels())
