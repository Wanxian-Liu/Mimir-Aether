"""第27单（2026-10-07）— 受控（预期）投递失败必须**不出声**。

事故：n8 投递双控 job 的正控臂**按设计**投一个不存在的 chat_id，它的失败被
N12 告警器当成真事故推给 HOME ⇒ 操作者每 12h 收到一条形态与**真事故完全一样**
的假警报（实证 2026-10-07T03:59:57Z · job 71ea0213e413）。

本文件的三条控制（缺一不可）：
1. 受控失败 ⇒ 台账有 `expected=true` 行、**零投递**（不推人）。
2. 同一次运行里的**非预期**失败 ⇒ 照旧出声（改分级 ≠ 关警报）。
3. 受控行不得吃掉真告警的冷却窗口（否则假警报的修法变成真警报的哑因）。
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import cron.delivery_alerts as da
import gateway.cron_mixin as cron_mixin
import gateway.delivery as delivery_mod
from gateway.config import Platform
from gateway.delivery import DeliveryRouter

SHEBANG = "#!" + "/" + "bin/bash" + chr(10)
BAD = "feishu:oc_00000000000000000000000000000000"
OTHER_BAD = "feishu:oc_deadbeef"


class Adapter:
    """与真实适配器同形：**返回**失败，不抛异常。"""

    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)
        self.sent = []

    async def send(self, chat_id, content, metadata=None):
        self.sent.append((chat_id, content))
        if chat_id in self.fail_for:
            return SimpleNamespace(success=False, error="invalid receive_id", message_id=None)
        return SimpleNamespace(success=True, message_id="om_ok", error=None)


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
    monkeypatch.setattr(da, "get_mimir_home", lambda: tmp_home)
    monkeypatch.setattr(gw_session, "build_session_context", lambda *a, **k: {})
    monkeypatch.setattr(gw_session, "build_session_context_prompt", lambda *a, **k: "")
    monkeypatch.setattr(gw_session_ctx, "set_session_vars", lambda **k: [])
    monkeypatch.setattr(gw_session_ctx, "clear_session_vars", lambda tokens: None)
    monkeypatch.setattr(cron_jobs, "mark_job_run", lambda *a, **k: None)
    monkeypatch.setattr(cron_jobs, "mark_job_delivery", lambda *a, **k: None)
    monkeypatch.setenv("FEISHU_HOME_CHANNEL", "oc_home")


def _script(tmp_home):
    p = tmp_home / "scripts" / "n27_echo.sh"
    p.write_text(SHEBANG + "set -u" + chr(10) + "echo n27-payload" + chr(10), encoding="utf-8")
    p.chmod(0o755)
    return "n27_echo.sh"


def _ledger(tmp_home):
    f = tmp_home / da.LEDGER_RELATIVE
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def _job(deliver, script, expected=None):
    job = {"id": "n27-e2e", "name": "n27 e2e", "script": script, "deliver": deliver, "prompt": ""}
    if expected is not None:
        job["expected_failures"] = expected
    return job

# ------------------------------------------------------------ unit: 纯函数
def test_expected_failure_map_accepts_both_spellings():
    assert da.expected_failure_map({"expected_failures": {BAD: "positive"}}) == {BAD: "positive"}
    assert da.expected_failure_map({"expected_failure_targets": [BAD]}) == {BAD: "expected"}
    # 畸形 spec ⇒ 「什么都不预期」= 安全方向（宁可警报吵，不可警报哑）
    assert da.expected_failure_map(None) == {}
    assert da.expected_failure_map({"expected_failures": "oops"}) == {}
    assert da.expected_failure_map({"expected_failure_targets": {"a": 1}}) == {}


def test_split_failures_keeps_both_sides():
    exp, unexp = da.split_failures(
        {BAD: "invalid receive_id", OTHER_BAD: "boom"}, {BAD: "positive"}
    )
    assert exp == {BAD: "invalid receive_id"}
    assert unexp == {OTHER_BAD: "boom"}


def test_expected_rows_do_not_consume_the_real_cooldown(tmp_path):
    """受控行 ≠ 冷却占用；**同一用例内给反证**（真告警行确实占用）。"""
    from datetime import datetime, timedelta, timezone

    ledger = tmp_path / "alerts.jsonl"
    t0 = datetime(2026, 10, 7, 4, 0, tzinfo=timezone.utc)
    da.record_alert(
        "job-1", "j", {BAD: "invalid receive_id"}, False,
        expected=True, control="positive", now=t0, path=ledger,
    )
    assert da.should_alert(
        "job-1", now=t0 + timedelta(seconds=1), cooldown_s=1800, path=ledger
    ) is True, "受控行吃掉了真告警的冷却窗口"
    da.record_alert("job-1", "j", {OTHER_BAD: "boom"}, True, now=t0 + timedelta(seconds=2), path=ledger)
    assert da.should_alert(
        "job-1", now=t0 + timedelta(seconds=3), cooldown_s=1800, path=ledger
    ) is False, "真告警行本应占用冷却（说明上一条断言不是恒真）"


# --------------------------------------------------- e2e: execute_cron_job
def test_e2e_expected_failure_is_recorded_and_silent(tmp_path, monkeypatch):
    """① 受控失败 ⇒ 台账有 expected 行 + **零告警投递**。"""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = Adapter(fail_for={"oc_00000000000000000000000000000000"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(_job(BAD, _script(tmp_home), {BAD: "positive"}))
    )

    recs = _ledger(tmp_home)
    assert len(recs) == 1, recs
    assert recs[0]["expected"] is True and recs[0]["control"] == "positive"
    assert recs[0]["delivered"] is False and recs[0]["send_error"] is None
    assert BAD in recs[0]["failed_targets"]
    # 只有控制臂自己那一次投递尝试；**没有**第二条 HOME 告警
    assert [c for c, _ in adapter.sent] == ["oc_00000000000000000000000000000000"], adapter.sent


def test_e2e_unexpected_failure_still_speaks(tmp_path, monkeypatch):
    """② 改分级 ≠ 关警报：非预期失败照旧投 HOME。"""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = Adapter(fail_for={"oc_00000000000000000000000000000000"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(
            _job(BAD, _script(tmp_home), {OTHER_BAD: "positive"})  # BAD 不在预期集里
        )
    )

    recs = _ledger(tmp_home)
    assert len(recs) == 1, recs
    assert recs[0]["expected"] is False and recs[0]["delivered"] is True
    assert adapter.sent[-1][0] == "oc_home", adapter.sent


def test_e2e_mixed_run_records_expected_and_alerts_on_the_real_one(tmp_path, monkeypatch):
    """③ 同一次运行两臂都有：受控臂只记账，真故障出声（两行台账）。"""
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = Adapter(fail_for={"oc_00000000000000000000000000000000", "oc_deadbeef"})
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}))

    asyncio.new_event_loop().run_until_complete(
        host.execute_cron_job(
            _job([BAD, OTHER_BAD], _script(tmp_home), {BAD: "positive"})
        )
    )

    recs = _ledger(tmp_home)
    assert len(recs) == 2, recs
    expected_rows = [r for r in recs if r["expected"]]
    alert_rows = [r for r in recs if not r["expected"]]
    assert len(expected_rows) == 1 and BAD in expected_rows[0]["failed_targets"]
    assert len(alert_rows) == 1 and OTHER_BAD in alert_rows[0]["failed_targets"]
    assert alert_rows[0]["delivered"] is True
    assert adapter.sent[-1][0] == "oc_home"
