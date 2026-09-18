"""N12 (2026-09-18) - delivery failures must alert on the EVENT.

Context: N8/N9 made delivery failures *visible* (`last_status="delivery_failed"`,
a WARNING line). Loki's 2026-09-18 04:12 review pointed at what pausing the 12h
`n9-report` poll left behind: a **blind window**. Nobody reads the job list
between polls, so an outage would sit unnoticed. An outage is an event, so the
alert must fire on the event.

Controls, both required (same discipline as N8/N9):
  * SUCCESS must produce **no** alert (otherwise "always alerts" passes),
  * a broken HOME channel must still be recorded (`delivered=false`) instead of
    collapsing into "no alert at all".
"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

import pytest

import cron.delivery_alerts as da
import gateway.cron_mixin as cron_mixin
import gateway.delivery as delivery_mod
from gateway.config import Platform
from gateway.delivery import DeliveryRouter

SHEBANG = "#!" + "/" + "bin/bash" + chr(10)


@dataclass
class SendResultLike:
    """Mirror of the real adapters: they RETURN, they do not raise."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class SelectiveAdapter:
    """Fails only for the destinations it was told to fail (like a real API)."""

    def __init__(self, fail_for=(), error="{'code': 230001, 'msg': 'invalid receive_id'}"):
        self.fail_for = set(fail_for)
        self.error = error
        self.sent = []

    async def send(self, chat_id, content, metadata=None):
        self.sent.append((chat_id, content))
        if chat_id in self.fail_for:
            return SendResultLike(success=False, error=self.error)
        return SendResultLike(success=True, message_id="om_ok")


@pytest.fixture(autouse=True)
def _home(monkeypatch):
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")


# ------------------------------------------------------- unit: ledger + gate
def test_should_alert_on_first_failure(tmp_path):
    ledger = tmp_path / "alerts.jsonl"
    assert da.should_alert("job-1", path=ledger) is True


def test_cooldown_suppresses_then_expires(tmp_path):
    """Rule 3: a job failing every minute must not storm notifications."""
    ledger = tmp_path / "alerts.jsonl"
    t0 = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    da.record_alert("job-1", "j", {"feishu:bad": "x"}, True, now=t0, path=ledger)
    assert da.should_alert("job-1", now=t0 + timedelta(seconds=60), cooldown_s=1800, path=ledger) is False
    assert da.should_alert("job-1", now=t0 + timedelta(seconds=1801), cooldown_s=1800, path=ledger) is True
    # a different job is not affected by another job's cooldown
    assert da.should_alert("job-2", now=t0 + timedelta(seconds=1), cooldown_s=1800, path=ledger) is True


def test_format_alert_carries_job_target_and_reason():
    text = da.format_alert("job-1", "nightly", {"feishu:oc_bad": "invalid receive_id"})
    assert "job-1" in text and "nightly" in text
    assert "feishu:oc_bad" in text and "invalid receive_id" in text


def test_malformed_ledger_lines_do_not_break_the_gate(tmp_path):
    ledger = tmp_path / "alerts.jsonl"
    ledger.write_text("not json\n{" + chr(34) + "job_id" + chr(34) + ": " + chr(34) + "other" + chr(34) + "}\n", encoding="utf-8")
    assert da.should_alert("job-1", path=ledger) is True


# ------------------------------------------------- e2e: through execute_cron_job
class _FakeEntry:
    session_key = "cron:key"
    session_id = "cron:session"


class _FakeStore:
    def get_or_create_session(self, source):
        return _FakeEntry()


class _Host(cron_mixin.CronMixin):
    def __init__(self, router):
        self.config = SimpleNamespace()
        self.session_store = _FakeStore()
        self.adapters = dict(router.adapters)
        self.delivery_router = router
        self._running_agents = {}
        self._background_tasks = set()


def _install(monkeypatch, tmp_home):
    import cron.jobs as cron_jobs
    import gateway.session as gw_session
    import gateway.session_context as gw_session_ctx

    (tmp_home / "scripts").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cron_mixin, "get_hermes_home", lambda: str(tmp_home))
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_home)
    # N12: the ledger must land under the test home, never the real one.
    monkeypatch.setattr(da, "get_mimir_home", lambda: tmp_home)
    monkeypatch.setattr(gw_session, "build_session_context", lambda *a, **k: {})
    monkeypatch.setattr(gw_session, "build_session_context_prompt", lambda *a, **k: "")
    monkeypatch.setattr(gw_session_ctx, "set_session_vars", lambda **k: [])
    monkeypatch.setattr(gw_session_ctx, "clear_session_vars", lambda tokens: None)
    monkeypatch.setattr(cron_jobs, "mark_job_run", lambda *a, **k: None)
    monkeypatch.setattr(cron_jobs, "mark_job_delivery", lambda *a, **k: None)


def _script(tmp_home):
    p = tmp_home / "scripts" / "n12_echo.sh"
    p.write_text(SHEBANG + "set -u" + chr(10) + "echo n12-payload" + chr(10), encoding="utf-8")
    p.chmod(0o755)
    return "n12_echo.sh"


def _job(deliver, script):
    return {"id": "n12-e2e", "name": "n12 e2e", "script": script, "deliver": deliver, "prompt": ""}


def _ledger(tmp_home):
    return [json.loads(l) for l in (tmp_home / da.LEDGER_RELATIVE).read_text(encoding="utf-8").splitlines() if l.strip()]


def test_e2e_failure_alerts_the_home_channel(tmp_path, monkeypatch):
    """POSITIVE: the job target is dead, the alert still reaches home."""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = SelectiveAdapter(fail_for={"oc_bad"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(_job("feishu:oc_bad", _script(tmp_home)))
    )

    recs = _ledger(tmp_home)
    assert len(recs) == 1, recs
    assert recs[0]["job_id"] == "n12-e2e" and recs[0]["delivered"] is True
    assert "feishu:oc_bad" in recs[0]["failed_targets"]
    # the alert went to HOME, not to the target that just failed
    assert adapter.sent[-1][0] == "oc_home"
    assert "n12-payload" in adapter.sent[0][1]


def test_e2e_success_produces_no_alert(tmp_path, monkeypatch):
    """CONTROL 1: success must stay silent (no 'always alerts' pass)."""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = SelectiveAdapter(fail_for=set())
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(_job("feishu:oc_ok", _script(tmp_home)))
    )

    assert not (tmp_home / da.LEDGER_RELATIVE).exists()
    assert len(adapter.sent) == 1


def test_e2e_second_failure_inside_cooldown_is_suppressed(tmp_path, monkeypatch):
    """Rule 3 through the real path: two runs, one alert."""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = SelectiveAdapter(fail_for={"oc_bad"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))
    job = _job("feishu:oc_bad", _script(tmp_home))

    loop = asyncio.new_event_loop()
    loop.run_until_complete(host.execute_cron_job(job))
    loop.run_until_complete(host.execute_cron_job(job))

    assert len(_ledger(tmp_home)) == 1, _ledger(tmp_home)


def test_e2e_broken_home_channel_is_recorded_not_silent(tmp_path, monkeypatch):
    """CONTROL 2: if home is broken too, the ledger still says so."""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = SelectiveAdapter(fail_for={"oc_bad", "oc_home"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(_job("feishu:oc_bad", _script(tmp_home)))
    )

    recs = _ledger(tmp_home)
    assert len(recs) == 1
    assert recs[0]["delivered"] is False and recs[0]["send_error"]


def test_e2e_missing_home_channel_is_recorded(tmp_path, monkeypatch):
    """No home channel at all -> recorded, and the cron run itself survives."""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)
    adapter = SelectiveAdapter(fail_for={"oc_bad"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(_job("feishu:oc_bad", _script(tmp_home)))
    )

    recs = _ledger(tmp_home)
    assert len(recs) == 1
    assert recs[0]["delivered"] is False
    assert "home channel" in (recs[0]["send_error"] or "")
