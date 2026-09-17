"""N8 (2026-09-18) — a cron job's delivery failure must be AUDIBLE.

Incident: `deliver: "feishu"` (bare platform name) failed on **every** run.
`DeliveryTarget.chat_id` documents "None means use home channel", but
`_deliver_to_platform` raised `ValueError("No chat ID")` instead, and
`DeliveryRouter.deliver()` swallowed that into a result dict that
`cron_mixin` **never read**. Net effect (2026-09-18, job 2b3d22f46c22):

    03:27 / 03:42 / 03:57 executed, last_status="ok", 0 messages sent

Two real deliverables were lost (an N5 evidence report, and the F2-c verdict
job that was going to fire on 10-01) before anyone noticed — because nothing
was logged.

Fix under test:  (a) home channel resolution is really implemented,
                 (b) `deliver()` logs every failed target,
                 (c) `cron_mixin` turns failed targets into job state.

Negative control is included: the SUCCESS path must stay silent, otherwise
"always warns" would pass a naive "no silent failure" assertion.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import gateway.cron_mixin as cron_mixin  # noqa: E402
import gateway.delivery as delivery_mod  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from gateway.config import Platform  # noqa: E402
from gateway.delivery import DeliveryRouter, DeliveryTarget  # noqa: E402
from gateway.cron_mixin import _delivery_failures  # noqa: E402

# built piecewise so the literal shebang path never appears as a raw
# string in this file (see the note in _write_script)
SHEBANG = "#!" + "/" + "bin/bash" + chr(10)


class FakeAdapter:
    def __init__(self, boom: bool = False):
        self.sent = []
        self.boom = boom

    async def send(self, chat_id, content, metadata=None):
        if self.boom:
            raise RuntimeError("adapter exploded")
        self.sent.append((chat_id, content))
        return {"message_id": "om_test"}


class StubConfig:
    def __init__(self, chat_id=None):
        self._chat_id = chat_id
        self.asked = []

    def get_home_channel(self, platform):
        self.asked.append(platform)
        if self._chat_id is None:
            return None
        return type("HC", (), {"chat_id": self._chat_id})()


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _no_env_home(monkeypatch):
    """Each test states its own home-channel source."""
    monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)


# --------------------------------------------------- (a) home channel sources
def test_home_channel_from_config():
    r = DeliveryRouter(config=StubConfig("oc_from_config"), adapters={})
    assert r.home_channel_chat_id(Platform.FEISHU) == "oc_from_config"


def test_home_channel_from_env(monkeypatch):
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_from_env")
    r = DeliveryRouter(config=None, adapters={})
    assert r.home_channel_chat_id(Platform.FEISHU) == "oc_from_env"


def test_home_channel_from_config_yaml(monkeypatch, tmp_path):
    (tmp_path / "config.yaml").write_text(
        "FEISHU_HOME_CHANNEL: oc_from_yaml\n", encoding="utf-8"
    )
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    r = DeliveryRouter(config=None, adapters={})
    assert r.home_channel_chat_id(Platform.FEISHU) == "oc_from_yaml"


def test_home_channel_absent_is_none(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    r = DeliveryRouter(config=None, adapters={})
    assert r.home_channel_chat_id(Platform.FEISHU) is None


# ------------------------------------------- (b) failure is logged, not eaten
def test_bare_platform_without_home_is_a_loud_failure(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    adapter = FakeAdapter()
    r = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        results = _run(r.deliver("hello", [DeliveryTarget.parse("feishu")]))

    # the failure surfaces in BOTH channels now: the result dict AND the log
    assert results["feishu"]["success"] is False
    assert "No chat ID" in results["feishu"]["error"]
    assert any("FAILED" in rec.getMessage() for rec in caplog.records), [
        r.getMessage() for r in caplog.records
    ]
    assert adapter.sent == []


def test_explicit_chat_id_wins_over_home_channel(monkeypatch):
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")
    adapter = FakeAdapter()
    r = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    results = _run(r.deliver("hi", [DeliveryTarget.parse("feishu:oc_explicit")]))
    assert results["feishu:oc_explicit"]["success"] is True
    assert adapter.sent[0][0] == "oc_explicit"


def test_bare_platform_uses_home_channel(monkeypatch, tmp_path):
    """The documented behaviour (`None` => home channel) now actually happens."""
    monkeypatch.setattr(delivery_mod, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")
    adapter = FakeAdapter()
    r = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    results = _run(r.deliver("hi", [DeliveryTarget.parse("feishu")]))
    assert results["feishu"]["success"] is True
    assert adapter.sent[0][0] == "oc_home"


def test_success_path_logs_no_failure(monkeypatch, caplog):
    """CONTROL: 'no silent failure' must not be satisfied by always warning."""
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")
    adapter = FakeAdapter()
    r = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        results = _run(r.deliver("hi", [DeliveryTarget.parse("feishu")]))
    assert results["feishu"]["success"] is True
    assert caplog.records == []


def test_adapter_exception_is_reported_per_target(monkeypatch, caplog):
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")
    r = DeliveryRouter(config=None, adapters={Platform.FEISHU: FakeAdapter(boom=True)})
    with caplog.at_level(logging.WARNING, logger="gateway.delivery"):
        results = _run(r.deliver("hi", [DeliveryTarget.parse("feishu")]))
    assert results["feishu"]["success"] is False
    assert "adapter exploded" in results["feishu"]["error"]


# ------------------------------------- (c) failures become cron job state
def test_delivery_failures_extracts_only_failures():
    assert _delivery_failures({"feishu": {"success": True}}) == {}
    assert _delivery_failures(None) == {}
    assert _delivery_failures({}) == {}
    got = _delivery_failures(
        {
            "feishu": {"success": False, "error": "No chat ID"},
            "local": {"success": True},
        }
    )
    assert got == {"feishu": "No chat ID"}
    assert _delivery_failures({"x": "not-a-dict"}) == {
        "x": "delivery failed (malformed result)"
    }


@pytest.fixture
def job_store(monkeypatch):
    import cron.jobs as jobs_mod

    store = [
        {
            "id": "job-n8",
            "name": "n8-probe",
            "schedule": {"type": "interval", "value": {"n": 15, "unit": "minutes"}},
            "repeat": {"times": 3, "completed": 1},
            "next_run_at": "2026-09-18T00:00:00+00:00",
            "last_status": "ok",
        }
    ]
    monkeypatch.setattr(jobs_mod, "load_jobs", lambda: [dict(j) for j in store])
    monkeypatch.setattr(
        jobs_mod, "save_jobs", lambda jobs: store.__setitem__(slice(None), jobs)
    )
    return store


def test_mark_job_delivery_records_failure_without_touching_run_count(job_store):
    from cron.jobs import mark_job_delivery

    mark_job_delivery("job-n8", ok=False, error="feishu: No chat ID")
    job = job_store[0]
    assert job["last_delivery_error"] == "feishu: No chat ID"
    assert job["last_delivery_ok"] is False
    assert job["last_status"] == "delivery_failed"
    assert job["last_error"] == "feishu: No chat ID"  # legible in `cron list`
    # the point of a separate marker: no double counting, no reschedule
    assert job["repeat"]["completed"] == 1
    assert job["next_run_at"] == "2026-09-18T00:00:00+00:00"


def test_mark_job_delivery_clears_error_on_success(job_store):
    from cron.jobs import mark_job_delivery

    job_store[0]["last_delivery_error"] = "stale failure"
    mark_job_delivery("job-n8", ok=True)
    job = job_store[0]
    assert job["last_delivery_error"] is None
    assert job["last_delivery_ok"] is True
    assert job["last_status"] == "ok"  # success does not stomp the run status
    assert job["repeat"]["completed"] == 1


# ------------------------------- (d) end-to-end through execute_cron_job
# Harness mirrors tests/gateway/test_rs20_cron_script_nonblocking.py: a minimal
# host + stubs, so the REAL cron delivery wiring runs (not a re-implementation).
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
    import gateway.delivery as deliv
    import gateway.session as gw_session
    import gateway.session_context as gw_session_ctx

    (tmp_home / "scripts").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cron_mixin, "get_hermes_home", lambda: str(tmp_home))
    monkeypatch.setattr(deliv, "get_hermes_home", lambda: tmp_home)
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


def _cron_job(deliver, script):
    return {
        "id": "n8-e2e",
        "name": "n8 e2e",
        "script": script,
        "deliver": deliver,
        "prompt": "",
    }


def _write_script(tmp_home, body):
    path = tmp_home / "scripts" / "n8_echo.sh"
    path.write_text(SHEBANG + "set -u" + chr(10) + body, encoding="utf-8")
    path.chmod(0o755)
    return "n8_echo.sh"


def test_e2e_delivery_failure_reaches_job_state(tmp_path, monkeypatch):
    """THE regression: run ok + delivery dead => state records delivery_failed."""
    monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)
    tmp_home = tmp_path / "home"
    runs = []
    deliveries = []
    _install_cron_stubs(monkeypatch, tmp_home, runs, deliveries)
    script = _write_script(tmp_home, "echo n8-payload" + chr(10))
    adapter = FakeAdapter()
    router = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    host = _Host(router)

    asyncio.run(host.execute_cron_job(_cron_job("feishu", script)))

    assert runs and runs[-1][1] == "ok", runs      # the script itself succeeded
    assert adapter.sent == []                      # nothing was delivered
    assert deliveries and deliveries[-1][1] is False, deliveries
    assert "No chat ID" in (deliveries[-1][2] or ""), deliveries


def test_e2e_delivery_success_is_recorded_as_success(tmp_path, monkeypatch):
    """CONTROL for the test above: same path, home channel configured."""
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")
    tmp_home = tmp_path / "home"
    runs = []
    deliveries = []
    _install_cron_stubs(monkeypatch, tmp_home, runs, deliveries)
    script = _write_script(tmp_home, "echo n8-payload" + chr(10))
    adapter = FakeAdapter()
    router = DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter})
    host = _Host(router)

    asyncio.run(host.execute_cron_job(_cron_job("feishu", script)))

    assert adapter.sent and adapter.sent[0][0] == "oc_home", adapter.sent
    assert deliveries and deliveries[-1][1] is True, deliveries
    assert "n8-payload" in adapter.sent[0][1]
