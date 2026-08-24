"""P0-2 压缩回归单测 — 400消息 → 返回摘要而非 coroutine。

四方共识清单 P0-2：run_agent.py/core_loop.py 已 await —— 补单测
「400消息 → compress 返回 (List[Dict], CompressionResult) 而非 coroutine」。

背景（2026-08-02 P0 coroutine bug 教训，见 mimiraether-context-compressor 技能）：
context_compressor.compress 是 async def，若调用方 sync 无 await 会拿到 coroutine 对象，
再被 run_in_executor 包装 → "cannot unpack non-iterable coroutine object"。
本测试确保 compress 的 async 契约不被破坏：await 后必须是真 tuple。
"""
import asyncio
import os

import pytest

from agent.context_compressor import MimirContextCompressor, CompressionResult

# P2-1 (2026-08-19): MIMIR_COMPRESS_THRESHOLD_TOKENS env 覆盖会破坏本测试确定性——
# 测试构造 8000 context_length/0.5 threshold 期望 threshold=4000 必压缩，
# 若环境导出了该变量（生产/本地 shell），400 条消息 28700 tokens 可能 < env 阈值
# → 压缩不触发 → 断言失败。autouse fixture 隔离 env，保证测试在任何环境确定性通过。
@pytest.fixture(autouse=True)
def _isolate_compressor_env(monkeypatch):
    monkeypatch.delenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", raising=False)
    monkeypatch.delenv("MIMIR_COMPRESS_VERIFY", raising=False)


def _build_messages(n: int, content: str = "x" * 200) -> list:
    """构造 n 条 user/assistant 交替消息，每条 ~200 chars（确保 token 超阈值）。"""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"{content} msg-{i}"})
    return msgs


def _make_compressor():
    """小 context_length + 低阈值 → 400 条消息必触发压缩；api_key 假值避免真实调用。"""
    return MimirContextCompressor(
        model="test-model",
        context_length=8000,          # threshold_tokens = 4000
        threshold_percent=0.5,
        protect_first_n=3,
        protect_last_n=6,
        tail_token_budget=2000,
        api_key="fake-key",
        base_url="http://127.0.0.1:9",  # 不可达端口——若意外真调用会快速失败走模板摘要
    )


class TestCompressReturnsTupleNotCoroutine:
    def test_400_messages_returns_summary_tuple(self):
        """400 消息 → await compress → (List[Dict], CompressionResult)，摘要发生。"""
        compressor = _make_compressor()
        messages = _build_messages(400)

        async def _run():
            return await compressor.compress(messages)

        result = asyncio.run(_run())

        # 核心断言：返回真 tuple（若 compress 被 sync 调用/包装成 coroutine，此处失败）
        assert isinstance(result, tuple), (
            f"compress 返回 {type(result)} 而非 tuple —— coroutine 泄漏！"
        )
        msgs, info = result
        assert isinstance(msgs, list), f"msgs 类型错误: {type(msgs)}"
        assert isinstance(info, CompressionResult), f"info 类型错误: {type(info)}"

        # 摘要应真实发生：压缩后消息数减少，原始 400
        assert info.original_count == 400
        assert info.compressed_count < info.original_count, (
            f"压缩未生效: {info.compressed_count} >= {info.original_count}"
        )
        # 摘要模式：llm（mock 成功）或 template（mock 失败降级）均可，但不能是 "none"
        assert info.summary_mode in ("llm", "template"), f"summary_mode={info.summary_mode}"

    def test_await_result_is_not_coroutine_object(self):
        """防回归：await 的返回值绝不能是 coroutine（2026-08-02 P0 bug 的直接断言）。"""
        compressor = _make_compressor()
        messages = _build_messages(400)

        async def _run():
            out = await compressor.compress(messages)
            return out

        result = asyncio.run(_run())
        assert not asyncio.iscoroutine(result), "返回值是 coroutine —— await 链断裂！"
        assert not asyncio.iscoroutine(result[0]), "msgs 是 coroutine —— await 链断裂！"

    def test_small_conversation_returns_unchanged(self):
        """小会话（< 阈值）→ 原样返回，仍为 tuple（不破坏正常路径）。"""
        compressor = _make_compressor()
        messages = _build_messages(3)

        async def _run():
            return await compressor.compress(messages)

        msgs, info = asyncio.run(_run())
        assert isinstance(msgs, list)
        assert info.original_count == 3
        assert info.compressed_count == 3  # 未达阈值不压缩
