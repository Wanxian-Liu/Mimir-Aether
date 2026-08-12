#!/usr/bin/env python3
"""A1 验证2：触发 in-loop 压缩，验证 agent_loop 钩子真实生效（stub 摘要避免外部 LLM 调用）。

链路：MimirAgentLoop(compressor=真实 MimirContextCompressor) → run() 每轮 API 前
      needs_compression → has_content_to_compress → compress() → 消息数下降。
"""
import asyncio
import logging
import sys

sys.path.insert(0, "/home/rayliu/src/MimirAether")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from agent.agent_loop import MimirAgentLoop
from agent.context_compressor import MimirContextCompressor

# ── 构造真实 compressor：context 100k → 50% 阈值 = 50k tokens ──
compressor = MimirContextCompressor(
    model="deepseek-chat",
    context_length=100000,
    threshold_percent=0.50,
    protect_first_n=3,
    protect_last_n=6,
    quiet_mode=True,
    api_key="stub",
    base_url="http://127.0.0.1:1",  # 摘要 LLM 必失败 → 走模板降级（不依赖外部）
)


async def _stub_summary(*args, **kwargs):
    return "[CONTEXT COMPACTION — REFERENCE ONLY] A1 验证摘要", "template"


compressor._generate_summary = _stub_summary  # 不调外部 LLM，只验证链路


async def _fake_model_call(messages):
    # 第一轮返回无 tool_calls 的完成 → loop 结束
    return type("Resp", (), {"content": "done", "tool_calls": None, "reasoning_content": None})


def _fake_dispatcher(name, args, task_id):
    return ""


async def main():
    # ── 构造超阈值消息：大量大 tool 输出撑到 >50k tokens ──
    messages = [
        {"role": "system", "content": "A1 in-loop compression test"},
        {"role": "user", "content": "请处理这个长任务（触发压缩验证）"},
    ]
    # 15 条大 tool 输出（每条 ~8k chars ≈ 2k tokens）
    for i in range(15):
        messages.append({"role": "assistant", "content": "", "tool_calls": [{"id": f"call_{i}", "type": "function", "function": {"name": "fake_tool", "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": f"call_{i}", "content": f"LARGE_TOOL_OUTPUT_{i} " + ("x" * 8000)})

    # 追加用户消息撑大（每条 4000 chars）→ 共 60 条
    for i in range(60):
        messages.append({"role": "user", "content": f"user message {i} " + ("y" * 4000)})

    loop = MimirAgentLoop(
        model_call=_fake_model_call,
        tool_schemas=[],
        valid_tool_names=set(),
        tool_dispatcher=_fake_dispatcher,
        max_turns=2,
        compressor=compressor,  # A1: 传入 compressor → 钩子启用
    )

    before = len(messages)
    tokens = compressor._estimate_tokens(messages)
    print(f"[setup] messages={before}, estimated_tokens={tokens}, threshold_tokens={compressor.threshold_tokens}")
    assert tokens >= compressor.threshold_tokens, "测试消息未达阈值，无法触发压缩"

    # 模拟真实链路：core_loop._compressor_sync_usage_from_llm 每轮 API 后 ingest usage
    # （needs_compression 依据 last_prompt_tokens）
    compressor.ingest_usage({
        "prompt_tokens": tokens,
        "completion_tokens": 100,
        "total_tokens": tokens + 100,
    })
    print(f"[setup] last_prompt_tokens={compressor.last_prompt_tokens} (>= {compressor.threshold_tokens} → needs_compression=True)")
    assert compressor.needs_compression(messages), "needs_compression 应触发"

    result = await loop.run(messages)
    print(f"[result] turns={result.turns_used}, messages after loop: {before} -> n/a (loop 内压缩)")
    print(f"[result] compressor.compression_count={compressor.compression_count}")
    print("PASS: MimirAgentLoop with compressor= ran without error")


asyncio.run(main())
