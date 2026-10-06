"""S4 (2026-10-06) - agent 型 cron job 失败必须出声（AGENTS 规矩 4）。

背景（盘上实证）：`gateway/cron_mixin.py::execute_cron_job` 末尾旧形态
    if not str(final_text).strip(): return
⇒ agent 型 job 跑成 empty_content / api_failure 时 final_response 恒空 ⇒ 连投递都
不发生：台账记了 error，**没人被告知**（静默失败家族）。2026-10-06 刘哥点出两条
15:03 / 15:22 的 empty_content 白跑即是此形态。

四臂（两正两控，缺一不可——单臂会放过「总是告警」或「永不告警」）：
  A 正控：exit_reason=empty_content + 空正文 ⇒ 必须投递「未产出」播报
  B 控  ：自然收尾 + 有正文                 ⇒ 正文原样投递、不被失败文案污染
  C 控  ：失败 + 正文含 [SILENT]            ⇒ 仍必须出声（silence 只对成功生效）
  D 控  ：自然收尾 + 空正文                 ⇒ 保持静默（成功但没话说 ≠ 告警）
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

import pytest

import gateway.cron_mixin as cron_mixin
import gateway.delivery as delivery_mod
from gateway.config import Platform
from gateway.delivery import DeliveryRouter


@dataclass
class SendResultLike:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class RecordingAdapter:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, content, metadata=None):
        self.sent.append((chat_id, content))
        return SendResultLike(success=True, message_id="om_ok")


class _FakeEntry:
    session_key = "cron:key"
    session_id = "cron:session"


class _FakeStore:
    def get_or_create_session(self, source):
        return _FakeEntry()


RUNS = []


class _Host(cron_mixin.CronMixin):
    """CronMixin + 一个可编排的 _run_agent（不碰真模型）。"""

    def __init__(self, router, agent_result):
        self.config = SimpleNamespace()
        self.session_store = _FakeStore()
        self.adapters = dict(router.adapters)
        self.delivery_router = router
        self._running_agents = {}
        self._background_tasks = set()
        self._agent_result = agent_result

    async def _run_agent(self, **kwargs):
        RUNS.append(kwargs)
        return self._agent_result


def _install(monkeypatch, tmp_home):
    import cron.delivery_alerts as da
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
    monkeypatch.setattr(cron_jobs, "mark_job_run", lambda *a, **k: LEDGER.append((a, k)))
    monkeypatch.setattr(cron_jobs, "mark_job_delivery", lambda *a, **k: None)
    # S4：告警台账必须落在 tmp_home，绝不写真家（N12 同纪律）
    monkeypatch.setattr(da, "get_mimir_home", lambda: tmp_home)
    # 2026-10-06 复核 #1：arm E 的 HOME 通道必须**真实可解析**。告警目标走生产
    # resolver `DeliveryRouter.home_channel_chat_id()`，三源优先级
    # gateway_config -> env -> config_yaml；用例的 config=None，故必须给后两源之一。
    # 这里用 `/sethome` 落盘的那种（config.yaml 的 FEISHU_HOME_CHANNEL），并清掉进程
    # env 同名变量——否则读数被运行环境的 FEISHU_HOME_CHANNEL 污染。
    # 不 patch 实现方法本身：patch 实现 = 量具与实现同源，测不出解析错。
    monkeypatch.delenv("FEISHU_HOME_CHANNEL", raising=False)
    (tmp_home / "config.yaml").write_text(
        "FEISHU_HOME_CHANNEL: oc_ok\n", encoding="utf-8"
    )


LEDGER = []


def _job(deliver="feishu:oc_ok"):
    return {"id": "s4-e2e", "name": "s4 周报", "script": None,
            "deliver": deliver, "prompt": "写周报 [tier:短]"}


def _run(tmp_path, monkeypatch, agent_result, deliver="feishu:oc_ok"):
    LEDGER.clear()
    RUNS.clear()
    tmp_home = tmp_path / "home"
    _install(monkeypatch, tmp_home)
    adapter = RecordingAdapter()
    host = _Host(DeliveryRouter(config=None, adapters={Platform.FEISHU: adapter}), agent_result)
    asyncio.new_event_loop().run_until_complete(host.execute_cron_job(_job(deliver)))
    return adapter.sent, list(LEDGER)


# ---------------------------------------------------------------- arm A (正控)
def test_failure_with_empty_body_is_delivered(tmp_path, monkeypatch):
    """A：empty_content + 空正文 ⇒ 必须有一条非空失败播报被投递。"""
    sent, ledger = _run(tmp_path, monkeypatch, {
        "final_response": "", "exit_reason": "empty_content", "failed": True,
    })
    assert sent, "旧形态：空正文直接 return ⇒ 一条都没投递（这就是要治的静默失败）"
    hits = [(c, t) for c, t in sent if c == "oc_ok" and "未产出" in t]
    assert hits, sent
    assert hits[0][1].strip() and "s4 周报" in hits[0][1], hits
    # 台账仍记 error（口径不变，双层）
    assert ledger and ledger[-1][0][1] == "error", ledger


# ---------------------------------------------------------------- arm B (控)
def test_success_body_is_delivered_verbatim(tmp_path, monkeypatch):
    """B：成功 ⇒ 正文原样投递，不得被失败文案污染。"""
    sent, ledger = _run(tmp_path, monkeypatch, {
        "final_response": "本周期观察：无异常。", "exit_reason": "natural",
    })
    assert [t for c, t in sent if c == "oc_ok"] == ["本周期观察：无异常。"], sent
    assert all("未产出" not in t for _c, t in sent), sent
    assert ledger and ledger[-1][0][1] == "ok", ledger


# ---------------------------------------------------------------- arm C (控)
def test_silent_marker_cannot_swallow_a_failure(tmp_path, monkeypatch):
    """C：失败 + [SILENT] ⇒ 仍必须出声（silence 只对成功生效）。"""
    sent, ledger = _run(tmp_path, monkeypatch, {
        "final_response": "[SILENT] nothing", "exit_reason": "empty_content", "failed": True,
    })
    assert sent, "[SILENT] 把失败吞掉了 ⇒ 又一条静默失败"
    assert ledger and ledger[-1][0][1] == "error", ledger


# ---------------------------------------------------------------- arm D (控)
def test_ok_with_empty_body_stays_silent(tmp_path, monkeypatch):
    """D：成功但没话说 ⇒ 保持静默（不许把「无话可说」变成告警）。"""
    sent, ledger = _run(tmp_path, monkeypatch, {
        "final_response": "", "exit_reason": "natural",
    })
    assert sent == [], sent


# ---------------------------------------------------------------- 预算臂
def test_tier_declaration_in_cron_prompt_is_honoured():
    """④ 额度上限：job.prompt 里的 [tier:短] 必须被现有分档机制解析成 20 轮。

    复用现有机制（agent/max_turns_tier.resolve_max_turns_tier）——不新建预算系统。
    """
    sys.path.insert(0, "/home/rayliu/src/MimirAether")
    from agent.max_turns_tier import resolve_max_turns_tier

    turns, tier, cleaned = resolve_max_turns_tier("写周报 [tier:短]", default=90)
    assert turns == 20, (turns, tier)
    assert tier == "short"
    assert "[tier:短]" not in cleaned, cleaned


# ---------------------------------------------------------------- arm E (正控)
def test_deliver_local_failure_still_reaches_home(tmp_path, monkeypatch):
    """E：job.deliver="local"（周报的实际配置）⇒ 失败仍必须到达 HOME 通道。

    只投 job 自己的 targets 时，local 目标 = 没人被告知 ⇒ 规矩 4 不成立。
    """
    sent, ledger = _run(tmp_path, monkeypatch, {
        "final_response": "", "exit_reason": "empty_content", "failed": True,
    }, deliver="local")
    # deliver="local" ⇒ 不该有 job-target 投递；那条投递只能是 HOME 告警。
    # 2026-10-06 复核 #1：只按文案过滤会放过「发到别处」，故先钉住投递地址。
    assert [c for c, _t in sent] == ["oc_ok"], f"deliver=local 却有多余投递：{sent}"
    home_hits = [(c, t) for c, t in sent if c == "oc_ok" and "跑失败" in t]
    assert home_hits, f"HOME 通道没收到失败告警：{sent}"
    _chat, text = home_hits[0]
    assert "s4 周报" in text and "empty_content" in text, text
    assert ledger and ledger[-1][0][1] == "error", ledger


# ---------------------------------------------------------------- arm F (控)
def test_success_sends_no_home_alert(tmp_path, monkeypatch):
    """F：成功 ⇒ 不得往 HOME 通道发告警（否则「总是告警」也能过 E 臂）。"""
    sent, ledger = _run(tmp_path, monkeypatch, {
        "final_response": "本周期观察：无异常。", "exit_reason": "natural",
    }, deliver="local")
    assert [t for _c, t in sent if "跑失败" in t] == [], sent
    assert ledger and ledger[-1][0][1] == "ok", ledger


def test_job_failure_alert_text_is_honest():
    """文案臂：失败播报必须含原因，且不得自称投递失败（那是另一类事件）。"""
    from cron.delivery_alerts import format_job_failure_alert

    text = format_job_failure_alert("s4-e2e", "s4 周报", "agent abnormal exit: empty_content")
    assert "empty_content" in text and "s4 周报" in text and "s4-e2e" in text
    assert "投递失败" not in text
