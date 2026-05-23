"""Stub LLM response objects for tests/agent/."""

from __future__ import annotations

from typing import Any, List


class MockChoice:
    def __init__(self, message: Any) -> None:
        self.message = message


class MockMessage:
    def __init__(
        self,
        content: str = "",
        tool_calls: List[dict] | None = None,
        reasoning_content: str | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []
        self.reasoning_content = reasoning_content


class MockResponse:
    def __init__(self, choices: List[MockChoice]) -> None:
        self.choices = choices
