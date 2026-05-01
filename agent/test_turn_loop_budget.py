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


class DummyBudgetMutable:
    """Budget with adjustable remaining (for reset / multi-turn scenarios)."""

    def __init__(self, remaining: int):
        self.remaining = remaining
        self._used = 0

    async def get_remaining(self) -> int:
        return self.remaining


class DummyAgentMutableBudget:
    def __init__(self, budget: DummyBudgetMutable):
        self.budget = budget
        self.chat_calls = 0

    async def chat(self, user_message: str) -> str:
        self.chat_calls += 1
        return f"echo:{user_message}"

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


def test_turn_manager_budget_exhausted_turn_fields_and_pointers():
    agent = DummyAgent(remaining=0)
    mgr = TurnManager(agent=agent)

    msg = asyncio.run(mgr.execute_turn("blocked"))
    assert "迭代次数已达上限" in msg

    turn = mgr.turns[0]
    assert turn.assistant_message is None
    assert turn.status == TurnStatus.MAX_ITERATIONS
    assert turn.error == "迭代次数已达上限"
    assert turn.iterations == 0
    assert mgr.current_turn is turn

    hist = mgr.get_turn_history()
    assert len(hist) == 1
    assert hist[0]["status"] == "max_iterations"
    assert hist[0]["error"] == "迭代次数已达上限"

    last = mgr.get_last_turn()
    assert last is turn

    stats = mgr.get_statistics()
    assert stats["total_turns"] == 1
    assert stats["max_iterations"] == 1
    assert stats["running"] == 0
    assert stats["completed"] == 0
    assert stats["failed"] == 0


def test_turn_manager_budget_exhausted_each_user_message_gets_own_turn():
    agent = DummyAgent(remaining=0)
    mgr = TurnManager(agent=agent)

    asyncio.run(mgr.execute_turn("first"))
    asyncio.run(mgr.execute_turn("second"))

    assert agent.chat_called is False
    assert len(mgr.turns) == 2
    assert all(t.status == TurnStatus.MAX_ITERATIONS for t in mgr.turns)
    assert mgr.turns[0].user_message == "first"
    assert mgr.turns[1].user_message == "second"
    assert mgr.current_turn is mgr.turns[-1]

    stats = mgr.get_statistics()
    assert stats["total_turns"] == 2
    assert stats["max_iterations"] == 2


def test_turn_manager_reset_after_exhausted_allows_normal_turn():
    budget = DummyBudgetMutable(remaining=0)
    agent = DummyAgentMutableBudget(budget=budget)
    mgr = TurnManager(agent=agent)

    out1 = asyncio.run(mgr.execute_turn("no budget"))
    assert "迭代次数已达上限" in out1
    assert agent.chat_calls == 0
    assert len(mgr.turns) == 1

    asyncio.run(mgr.reset())
    assert len(mgr.turns) == 0
    assert mgr.current_turn is None

    budget.remaining = 3
    out2 = asyncio.run(mgr.execute_turn("after reset"))
    assert out2 == "echo:after reset"
    assert agent.chat_calls == 1
    assert len(mgr.turns) == 1
    assert mgr.turns[0].status == TurnStatus.COMPLETED
    assert mgr.current_turn is mgr.turns[0]

