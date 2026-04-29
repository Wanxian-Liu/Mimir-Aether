import asyncio

import pytest

from agent.turn_loop import TurnManager, TurnStatus


class DummyBudget:
    def __init__(self, remaining: int):
        self._remaining = remaining

    async def get_remaining(self) -> int:
        return self._remaining


class DummyAgent:
    def __init__(self, remaining: int):
        self.budget = DummyBudget(remaining=remaining)
        self.chat_called = False

    async def chat(self, user_message: str) -> str:
        self.chat_called = True
        return "should-not-happen"

    async def reset(self) -> None:
        return None


def test_turn_manager_budget_exhausted_skips_chat():
    agent = DummyAgent(remaining=0)
    mgr = TurnManager(agent=agent)

    msg = asyncio.run(mgr.execute_turn("hello"))
    assert "迭代次数已达上限" in msg
    assert agent.chat_called is False

    assert len(mgr.turns) == 1
    assert mgr.turns[0].status == TurnStatus.MAX_ITERATIONS

