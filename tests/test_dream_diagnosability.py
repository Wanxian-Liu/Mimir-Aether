"""离线受控差分：梦境蒸馏「可诊化」正控 / 负控 —— 不打真 API。

正控：finish_reason="length" ⇒ ①记「截断」②抬 max_tokens 重发一次 ③失败件含原始载荷
负控：finish_reason="stop" + 合法 JSON ⇒ 一次成功、不重发
"""
import asyncio
import json
import logging
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="dreamdiag-")
os.environ["MIMIR_AETHER_HOME"] = TMP
os.environ["DEEPSEEK_API_KEY"] = "sk-" + "0" * 40

from agent import dream_memory as dm  # noqa: E402

MSGS = []


class Cap(logging.Handler):
    def emit(self, record):
        MSGS.append(record.getMessage())


dm.logger.addHandler(Cap())
dm.logger.setLevel(logging.DEBUG)
MSG = "蒸馏未产出新数据（LLM 调用/解析失败），未修改"


def fake_factory(responses):
    calls = []

    async def _fake(prompt, max_tokens, api_key, base_url):
        calls.append(max_tokens)
        return responses[min(len(calls) - 1, len(responses) - 1)], None

    return _fake, calls


def run_pos():
    MSGS.clear()
    truncated = '{"key_decisions": ["x", "y"'
    resp = {
        "choices": [{"message": {"content": truncated}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 8702, "completion_tokens": 4096, "total_tokens": 12798},
    }
    fake, calls = fake_factory([resp, resp])
    dm._post_dream_chat = fake
    out = asyncio.run(dm._call_dream_llm("p"))
    assert out is None, out
    assert calls == [4096, 8192], calls
    assert any("输出被截断" in m for m in MSGS), MSGS
    d = dict(dm._LAST_DREAM_DIAG)
    assert d["retry_due_to"] == "length" and d["attempts"] == 2, d
    assert d["content"] == truncated and d["finish_reason"] == "length", d
    dm._record_failure("llm", RuntimeError(MSG))
    rec = json.load(
        open(os.path.join(TMP, "data", "dream_distill_failure.json"), encoding="utf-8")
    )
    for k in ("content", "finish_reason", "usage", "attempts"):
        assert k in rec, (k, sorted(rec))
    assert rec["content"] == truncated and rec["stage"] == "llm", rec
    return rec


def run_neg():
    MSGS.clear()
    resp = {
        "choices": [
            {"message": {"content": '{"key_decisions": ["a"]}'}, "finish_reason": "stop"}
        ],
        "usage": {"total_tokens": 10},
    }
    fake, calls = fake_factory([resp])
    dm._post_dream_chat = fake
    out = asyncio.run(dm._call_dream_llm("p"))
    assert out == {"key_decisions": ["a"]}, out
    assert calls == [4096], calls
    assert dm._LAST_DREAM_DIAG["attempts"] == 1, dm._LAST_DREAM_DIAG
    assert not any("截断" in m for m in MSGS), MSGS
    return out


if __name__ == "__main__":
    pos = run_pos()
    neg = run_neg()
    print("POS ok: calls 4096->8192 · failure keys =", sorted(pos.keys()))
    print("NEG ok: once · no retry · parsed =", neg)
    print("ALL CONTROLS PASS")
