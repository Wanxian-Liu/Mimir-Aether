"""B2 (2026-08-19 v2): on_task_start 重置 _parallel_read_nudge_done（防跨任务失效）。

背景：_parallel_read_nudge_done 语义为"每个任务最多注入一次并行读 nudge"。
__init__ 仅在实例创建时重置；若同一实例被复用执行多个任务，第二个任务
将因 flag 残留而不再收到 nudge。B2 新增 on_task_start 钩子，在 _loop_body
（每次 run 即每个任务）开头调用重置。

验证标准（执行卡 B2）：grep on_task_start 重置逻辑 + 测试。
"""

from unittest.mock import MagicMock

from agent.agent_loop import MimirAgentLoop


def _make_loop(**kwargs):
    """Helper to create a MimirAgentLoop with minimal required args."""
    return MimirAgentLoop(
        model_call=MagicMock(),
        tool_schemas=[],
        valid_tool_names=set(),
        tool_dispatcher=MagicMock(),
        **kwargs,
    )


class TestTaskStartReset:
    """on_task_start 钩子：任务开始时重置一次性 nudge 标志。"""

    def test_default_flag_is_false(self):
        """新实例默认 flag=False（__init__ 基线）。"""
        loop = _make_loop()
        assert loop._parallel_read_nudge_done is False

    def test_flag_reset_on_task_start(self):
        """模拟复用场景：上一任务已触发 nudge（flag=True），
        on_task_start 必须重置为 False。"""
        loop = _make_loop()
        loop._parallel_read_nudge_done = True  # 模拟上一任务已触发
        loop.on_task_start()
        assert loop._parallel_read_nudge_done is False

    def test_on_task_start_is_idempotent(self):
        """重复调用无副作用（连续重置不抛错、状态不变）。"""
        loop = _make_loop()
        loop.on_task_start()
        loop.on_task_start()
        assert loop._parallel_read_nudge_done is False
