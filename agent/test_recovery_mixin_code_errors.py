"""RecoveryMixin: code errors must not truncate in-memory history (IR-20260520)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.error_classifier import FailoverReason
from agent.recovery_mixin import RecoveryMixin
from agent.strategy_matcher import StrategyAction


class _RecoveryStub(RecoveryMixin):
    def __init__(self) -> None:
        self.model = "openrouter/test-model"
        self.decision_ring = MagicMock()
        self.decision_ring.decide.return_value = MagicMock(
            classified_error=MagicMock(reason=FailoverReason.unknown),
            suggested_actions=[],
        )
        self.compressor = MagicMock()
        self.budget = MagicMock()
        self.budget.stats = MagicMock()
        self._truncate_history = AsyncMock()
        self._clean_orphan_tools = MagicMock()


@pytest.mark.parametrize(
    "exc",
    [
        NameError("model_metadata is not defined"),
        ImportError("cannot import name 'MetricType'"),
        AttributeError("'NoneType' object has no attribute 'x'"),
        ModuleNotFoundError("No module named 'gateway._shared'"),
    ],
)
def test_code_errors_skip_truncate_and_compress(exc: Exception) -> None:
    stub = _RecoveryStub()
    recovered = asyncio.run(stub.handle_error_with_recovery(exc))
    assert recovered is False
    stub._truncate_history.assert_not_awaited()
    stub._clean_orphan_tools.assert_not_called()


def test_context_overflow_still_truncates() -> None:
    stub = _RecoveryStub()
    stub.decision_ring.decide.return_value = MagicMock(
        classified_error=MagicMock(reason=FailoverReason.context_overflow),
        suggested_actions=[StrategyAction.TRUNCATE_CONTEXT],
    )
    recovered = asyncio.run(
        stub.handle_error_with_recovery(RuntimeError("context length exceeded"))
    )
    assert recovered is True
    stub._truncate_history.assert_awaited()
