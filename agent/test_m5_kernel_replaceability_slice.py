"""M5 minimal slice: LlmInvocationPort is a stable replaceability seam (no network)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from agent.llm_port import LlmInvocationPort


class _StubA:
    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        return {"role": "assistant", "content": "A"}, 1.0


class _StubB:
    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        return {"role": "assistant", "content": "B"}, 2.0


def test_two_stubs_satisfy_llm_invocation_port() -> None:
    async def _run() -> None:
        a = _StubA()
        b = _StubB()
        assert isinstance(a, LlmInvocationPort)
        assert isinstance(b, LlmInvocationPort)
        out_a, lat_a = await a.call_model_with_tokens([], "s1")
        out_b, lat_b = await b.call_model_with_tokens([], "s1")
        assert out_a["content"] == "A" and lat_a == 1.0
        assert out_b["content"] == "B" and lat_b == 2.0

    asyncio.run(_run())


def test_missing_method_not_port() -> None:
    class Bad:
        pass

    assert not isinstance(Bad(), LlmInvocationPort)
