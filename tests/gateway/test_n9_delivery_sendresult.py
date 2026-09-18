"""N9 (2026-09-18) — adapter-REPORTED delivery failure must be audible.

N8 made *raised* delivery failures visible. Production then showed the other
half was still silent: real adapters do not raise on an API rejection, they
**return** `SendResult(success=False, error=...)`
(`gateway/platforms/feishu_adapter.py::send` -> `code=230001 invalid receive_id`).

Evidence (production, not the suite): cron job `44ff4165be31` (positive
control, 2026-09-18 10:53:33) delivered to a non-existent `chat_id`;
`gateway.log` got the Feishu "send failed" WARNING, yet `jobs.json` recorded
`last_status="ok"` / `last_delivery_ok=true`. The N8 tests missed it because
their fake adapter *raised* — a test double that did not mirror the real
contract.

Fix under test: `DeliveryRouter` inspects the adapter's returned result and
raises `DeliverySendError`, reusing N8's loud path.

Controls, both required:
  * SUCCESS result must stay silent (no "always warns" pass),
  * an UNKNOWN result shape must NOT be flagged (no false alarms).
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Optional

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import gateway.cron_mixin as cron_mixin  # noqa: E402
import gateway.delivery as delivery_mod  # noqa: E402
from gateway.config import Platform  # noqa: E402
from gateway.delivery import (  # noqa: E402
    DeliveryRouter,
    DeliverySendError,
    DeliveryTarget,
    _adapter_result_failure,
)

SHEBANG = "#!" + "/" + "bin/bash" + chr(10)


@dataclass
class SendResultLike:
    """Mirror of gateway.platforms.base.SendResult (attribute-based)."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class ReportingAdapter:
    """Adapter that behaves like the REAL ones: it returns, never raises."""

    def __init__(self, result: Any):
        self.result = result
        self.sent = []

    async def send(self, chat_id, content, metadata=None):
        self.sent.append((chat_id, content))
        return self.result


class StubConfig:
    def get_home_channel(self, platform):
        return None


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _home(monkeypatch):
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")


# ------------------------------------------------ unit: the returned result
def test_sendresult_failure_is_reported(caplog):
    """The exact production shape: Feishu rejects the destination."""
    api_err = "{'code': 230001, 'msg': 'invalid receive_id'}"
    adapter = ReportingAdapter(SendResultLike(success=False, error=api_err))
    router = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})

    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        results = _run(router.deliver("hi", [DeliveryTarget.parse("feishu:oc_bad")]))

    assert results["feishu:oc_bad"]["success"] is False, results
    assert "230001" in results["feishu:oc_bad"]["error"], results
    assert any("FAILED" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]


def test_dict_shaped_failure_is_reported():
    adapter = ReportingAdapter({"success": False, "error": "boom"})
    router = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    results = _run(router.deliver("hi", [DeliveryTarget.parse("feishu:oc_bad")]))
    assert results["feishu:oc_bad"]["success"] is False
    assert "boom" in results["feishu:oc_bad"]["error"]


def test_sendresult_success_path_stays_silent(caplog):
    """CONTROL 1: success must not be turned into a warning."""
    adapter = ReportingAdapter(SendResultLike(success=True, message_id="om_ok"))
    router = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        results = _run(router.deliver("hi", [DeliveryTarget.parse("feishu:oc_ok")]))
    assert results["feishu:oc_ok"]["success"] is True
    assert caplog.records == [], [r.getMessage() for r in caplog.records]
    assert adapter.sent[0][0] == "oc_ok"


def test_unknown_result_shape_is_not_a_false_alarm(caplog):
    """CONTROL 2: a shape we do not understand must NOT be called a failure.

    `{"message_id": "om_test"}` is exactly what the N8 fake returned.
    """
    adapter = ReportingAdapter({"message_id": "om_test"})
    router = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        results = _run(router.deliver("hi", [DeliveryTarget.parse("feishu:oc_ok")]))
    assert results["feishu:oc_ok"]["success"] is True
    assert caplog.records == []


def test_result_inspector_table():
    """The inspector itself: only explicit failures are failures."""
    assert _adapter_result_failure(None) is None
    assert _adapter_result_failure({"message_id": "om"}) is None
    assert _adapter_result_failure(SendResultLike(success=True)) is None
    assert "x" in _adapter_result_failure(SendResultLike(success=False, error="x"))
    # a failure with no message still produces a legible reason
    assert _adapter_result_failure(SendResultLike(success=False))
    assert _adapter_result_failure({"success": False})


def test_local_target_is_never_mistaken_for_a_failure(tmp_path, monkeypatch):
    """`_deliver_local` returns {"path": ...} — no `success` key."""
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    router = DeliveryRouter(config=None, adapters={})
    results = _run(router.deliver("hi", [DeliveryTarget.parse("local")]))
    assert results["local"]["success"] is True


# ------------------------------------------- e2e: through execute_cron_job
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


def _install_cron_stubs(monkeypatch, tmp_home, runs, deliveries):
    import cron.jobs as cron_jobs
    import gateway.session as gw_session
    import gateway.session_context as gw_session_ctx

    (tmp_home / "scripts").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cron_mixin, "get_hermes_home", lambda: str(tmp_home))
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_home)
    monkeypatch.setattr(gw_session, "build_session_context", lambda *a, **k: {})
    monkeypatch.setattr(gw_session, "build_session_context_prompt", lambda *a, **k: "")
    monkeypatch.setattr(gw_session_ctx, "set_session_vars", lambda **k: [])
    monkeypatch.setattr(gw_session_ctx, "clear_session_vars", lambda tokens: None)
    monkeypatch.setattr(
        cron_jobs,
        "mark_job_run",
        lambda job_id, status, error=None: runs.append((job_id, status, error)),
    )
    monkeypatch.setattr(
        cron_jobs,
        "mark_job_delivery",
        lambda job_id, ok, error=None: deliveries.append((job_id, ok, error)),
    )


def _write_script(tmp_home):
    path = tmp_home / "scripts" / "n9_echo.sh"
    path.write_text(SHEBANG + "set -u" + chr(10) + "echo n9-payload" + chr(10), encoding="utf-8")
    path.chmod(0o755)
    return "n9_echo.sh"


def _cron_job(deliver, script):
    return {"id": "n9-e2e", "name": "n9 e2e", "script": script, "deliver": deliver, "prompt": ""}


def test_e2e_reported_failure_reaches_job_state(tmp_path, monkeypatch):
    """THE regression: run ok + adapter reports failure => delivery_failed."""
    tmp_home = tmp_path / "home"
    runs, deliveries = [], []
    _install_cron_stubs(monkeypatch, tmp_home, runs, deliveries)
    script = _write_script(tmp_home)
    adapter = ReportingAdapter(
        SendResultLike(success=False, error="code=230001 invalid receive_id")
    )
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.run(host.execute_cron_job(_cron_job("feishu:oc_bad", script)))

    assert runs and runs[-1][1] == "ok", runs
    assert deliveries and deliveries[-1][1] is False, deliveries
    assert "230001" in (deliveries[-1][2] or ""), deliveries


def test_e2e_reported_success_is_recorded_as_success(tmp_path, monkeypatch):
    """CONTROL: same path, adapter reports success."""
    tmp_home = tmp_path / "home"
    runs, deliveries = [], []
    _install_cron_stubs(monkeypatch, tmp_home, runs, deliveries)
    script = _write_script(tmp_home)
    adapter = ReportingAdapter(SendResultLike(success=True, message_id="om_ok"))
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.run(host.execute_cron_job(_cron_job("feishu:oc_ok", script)))

    assert deliveries and deliveries[-1][1] is True, deliveries
    assert adapter.sent and "n9-payload" in adapter.sent[0][1]


def test_delivery_send_error_is_a_runtime_error():
    """Callers that catch broad exceptions keep working."""
    assert issubclass(DeliverySendError, RuntimeError)
