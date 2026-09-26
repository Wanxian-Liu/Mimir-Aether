"""计量透传回归（2026-09-26 · Mimir 定案）

被测改动：委派子代理的 api_calls / tokens / 工具轨迹此前在父侧**结构上恒 0 / 恒空**——
  - run_agent.AIAgent.run_conversation 硬编码 prompt/completion/total_tokens = 0，
    且 messages 回显**入参**历史（delegate 只传 goal ⇒ None ⇒ []）⇒ tool_trace 必空；
  - delegate_tool 读的 result["api_calls"] 全仓无产出点；
  - session_prompt_tokens/session_completion_tokens 被 getattr 读、**全仓无写入点** ⇒ 恒 0。

臂型标注（防「源码含某串」式假绿）：B = 行为级（跑真实函数）· S = 结构闸（只读源码）
"""
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


class _FakeCompressor:
    context_length = 1_000_000
    threshold_tokens = 120_000

    def __init__(self):
        self.ingested = []
        self.bound = None

    def bind_session(self, sid):
        self.bound = sid

    def ingest_usage(self, usage):
        self.ingested.append(usage)

    def settle_post_measure(self, *a, **k):
        return None


class _FakeRealAgent:
    """最小 MimirAetherAgent 替身：只提供适配层真正会碰的属性/方法。"""

    def __init__(self, response="child-answer", metrics=None, messages=None):
        self.model = "deepseek/deepseek-flash"
        self.compressor = _FakeCompressor()
        self.session_id = "sess-child"
        self._response = response
        self.last_run_metrics = {} if metrics is None else metrics
        self.last_run_messages = [] if messages is None else messages

    def run_conversation(self, user_message, conversation_history=None, **kw):
        return self._response


def _adapter(monkeypatch, fake):
    from run_agent import AIAgent

    ag = AIAgent()
    ag._real_agent = fake
    # run_conversation 内部 `from agent.async_bridge import run_async` 是局部导入，
    # 故 patch 模块属性即可命中；返回参数原样透传 ⇒ 测试无需事件循环。
    import agent.async_bridge as bridge
    monkeypatch.setattr(bridge, "run_async", lambda coro: coro, raising=True)
    return ag


MAXIMAL = {
    "turns_used": 5,
    "exit_reason": "max_turns",
    "interrupted": False,
    "tool_error_count": 0,
    "api_calls": 5,
    "prompt_tokens": 42_000,
    "completion_tokens": 700,
}

CHILD_MSGS = [
    {"role": "assistant", "tool_calls": [
        {"id": "c1", "function": {"name": "terminal", "arguments": '{"command":"ls"}'}},
    ]},
    {"role": "tool", "tool_call_id": "c1", "content": "ok"},
]


def test_adapter_passes_real_metrics(monkeypatch):
    """B：真值透传（api_calls / turns / tokens / 子代理自身轨迹）"""
    fake = _FakeRealAgent(metrics=MAXIMAL, messages=CHILD_MSGS)
    out = _adapter(monkeypatch, fake).run_conversation("goal-x")
    assert out["api_calls"] == 5
    assert out["turns_used"] == 5
    assert out["exit_reason"] == "max_turns"
    assert out["prompt_tokens"] == 42_000
    assert out["completion_tokens"] == 700
    assert out["total_tokens"] == 42_700
    assert out["metrics_available"] is True
    assert out["messages"] == CHILD_MSGS, "必须回传子代理自己的轨迹，而非入参回显"


def test_adapter_marks_unavailable_instead_of_fake_zero(monkeypatch, caplog):
    """B：指标缺失 ⇒ 显式 unavailable + WARNING（不伪装成 0）"""
    fake = _FakeRealAgent(metrics={}, messages=[])
    with caplog.at_level("WARNING"):
        out = _adapter(monkeypatch, fake).run_conversation(
            "goal-y", conversation_history=[{"role": "user", "content": "prior"}]
        )
    assert out["metrics_available"] is False
    assert out["turns_used"] == 0
    assert out["messages"] == [{"role": "user", "content": "prior"}]
    assert any("last_run_metrics" in r.getMessage() for r in caplog.records), \
        "指标缺失必须 fail-visible（留 WARNING），否则又是静默假绿"


def test_session_usage_accumulates(monkeypatch, tmp_path):
    """B：会话用量累加（两次真 usage ⇒ 求和）"""
    from agent.callers_mixin import CallersMixin

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    ag = _FakeRealAgent()
    msgs = [{"role": "user", "content": "hi"}]
    CallersMixin._compressor_sync_usage_from_llm(
        ag, {"usage": {"prompt_tokens": 1000, "completion_tokens": 10}}, msgs)
    CallersMixin._compressor_sync_usage_from_llm(
        ag, {"usage": {"prompt_tokens": 2500, "completion_tokens": 40}}, msgs)
    assert ag.session_prompt_tokens == 3500
    assert ag.session_completion_tokens == 50
    assert ag.session_api_calls == 2


def test_session_usage_ignores_missing_usage(monkeypatch, tmp_path):
    """B 负控：usage 未真报时不得把粗估计入会话用量"""
    from agent.callers_mixin import CallersMixin

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    ag = _FakeRealAgent()
    CallersMixin._compressor_sync_usage_from_llm(
        ag, {}, [{"role": "user", "content": "hi"}])
    assert getattr(ag, "session_prompt_tokens", 0) == 0
    assert getattr(ag, "session_completion_tokens", 0) == 0


def test_structural_session_tokens_have_writer():
    """S：session_prompt_tokens 必须存在**写入点**（防「零写入点 ⇒ 恒 0」复发）"""
    src = (REPO / "agent/callers_mixin.py").read_text(encoding="utf-8")
    writer = re.compile(r"self\.session_prompt_tokens\s*=")
    assert writer.search(src), "又变回只读不写 ⇒ 委派成本终将恒 0"
    # 负控：同一正则对「只读」形态不匹配（证明闸有鉴别力）
    assert not writer.search("x = getattr(child, 'session_prompt_tokens', 0)")


@pytest.mark.parametrize("key", [
    '"source": _tokens_source',
    '"turns_used": int(result.get("turns_used")',
    '"metrics_available": bool(result.get("metrics_available"',
])
def test_structural_delegate_entry_keys(key):
    """S：委派 entry 必须带成本口径字段（标注：结构闸，非行为级）"""
    src = (REPO / "tools/delegate_tool.py").read_text(encoding="utf-8")
    assert key in src, f"委派 entry 缺字段：{key}"
