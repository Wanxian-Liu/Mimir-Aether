"""E1 摘要写回测试 — compaction summary writeback（四方共识 E1 清单 S4）。

背景（2026-08-19 四方卡块4 E1）：
- 压缩只截断不写回 → D2 信息丢失（跨会话不可回溯）。
- 修复：compress() 成功且验证通过后 → 注入回调写回 event_data
  {summary, pruned_count, ts} 到 session_tracker（事件类型 context_compaction）。
- env 开关：MIMIR_COMPRESS_WRITEBACK（1=开默认 / 0=关）；MIMIR_COMPRESS_VERIFY 控制实体保留率验证。

三个断言组：
1. 回调收到 event_data（summary/pruned_count/ts 字段齐全）
2. 事件落 session_tracker（record_event → session_events 表可查）
3. 回退分支（实体保留率 <80%）不写回 + 质量告警落盘 compression_quality.jsonl
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from agent.context_compressor import (
    ContextCompressorV2,
    MimirContextCompressor,
    CompressionResult,
)


def _build_messages(n: int, content: str = "x" * 200) -> list:
    """构造 n 条 user/assistant 交替消息（对齐 test_context_compressor_await 模式）。"""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"{content} msg-{i}"})
    return msgs


def _make_compressor(**kw):
    """小 context_length + 低阈值 → 必触发压缩路径；api_key 假值避免真实调用。"""
    defaults = dict(
        model="test-model",
        context_length=8000,
        threshold_percent=0.5,
        protect_first_n=3,
        protect_last_n=6,
        tail_token_budget=2000,
        api_key="fake-key",
        base_url="http://127.0.0.1:9",
    )
    defaults.update(kw)
    return MimirContextCompressor(**defaults)


def _mock_base_compress(post_msgs, result):
    """patch 基类 ContextCompressorV2.compress（super().compress 返回 mock 结果）。

    关键：只 mock 基类——MimirContextCompressor.compress 覆写逻辑
    （实体保留率验证 + 回滚 + _emit_writeback）真实执行。
    """
    return patch.object(
        ContextCompressorV2,
        "compress",
        new=AsyncMock(return_value=(post_msgs, result)),
    )


@pytest.fixture
def verify_on(monkeypatch):
    """确保实体保留率验证开启（防环境残留 MIMIR_COMPRESS_VERIFY=0）。"""
    monkeypatch.setenv("MIMIR_COMPRESS_VERIFY", "1")
    return True


class TestWritebackCallbackReceivesEventData:
    """断言 1：压缩成功 → 回调收到含 summary/pruned_count/ts 的 event_data。"""

    def test_callback_receives_event_data(self, verify_on):
        compressor = _make_compressor()
        messages = _build_messages(400)
        captured = {}

        def _cb(event_data: dict) -> None:
            captured.update(event_data)

        compressor.set_writeback_callback(_cb)

        _result = CompressionResult(
            original_count=400,
            compressed_count=35,
            summary="[CONTEXT COMPACTION — REFERENCE ONLY] E1 test summary",
            pruned_tool_count=12,
            summary_mode="template",
        )
        _post = _build_messages(35, content="compacted")

        with _mock_base_compress(_post, _result):
            _msgs, _info = asyncio.run(compressor.compress(messages))

        # 回调必须被触发且拿到完整 event_data
        assert captured, "回调未被调用——写回缺失"
        assert "summary" in captured and captured["summary"]
        assert captured["pruned_count"] == 12
        assert "ts" in captured and captured["ts"]

    def test_callback_exception_does_not_break_compress(self, verify_on):
        """回调抛异常 → warning 降级，compress 仍返回正常结果（不阻断）。"""
        compressor = _make_compressor()
        messages = _build_messages(400)

        def _bad_cb(event_data: dict) -> None:
            raise RuntimeError("callback boom")

        compressor.set_writeback_callback(_bad_cb)

        _result = CompressionResult(
            original_count=400, compressed_count=35, summary="s",
            pruned_tool_count=3, summary_mode="template",
        )
        _post = _build_messages(35, content="compacted")

        with _mock_base_compress(_post, _result):
            _msgs, _info = asyncio.run(compressor.compress(messages))
        assert isinstance(_msgs, list)
        assert _info.compressed_count == 35  # 压缩结果未被回调异常破坏


class TestEventLandsInSessionTracker:
    """断言 2：回调把事件写进 session_tracker（事件类型 context_compaction）。"""

    def test_event_recorded_in_session_tracker(self, verify_on, tmp_path):
        compressor = _make_compressor()
        messages = _build_messages(400)
        _db = tmp_path / "sessions_e1.db"
        recorded = {}

        from agent.session_tracker import SessionTracker

        _tracker = SessionTracker(db_path=str(_db))
        _tracker.create_session("e1-session-001", {"source": "test"})

        def _cb(event_data: dict) -> None:
            _ok = _tracker.record_event("e1-session-001", "context_compaction", event_data)
            recorded["ok"] = _ok
            recorded["data"] = event_data

        compressor.set_writeback_callback(_cb)

        _result = CompressionResult(
            original_count=400, compressed_count=35, summary="E1 summary",
            pruned_tool_count=7, summary_mode="template",
        )
        _post = _build_messages(35, content="compacted")

        with _mock_base_compress(_post, _result):
            asyncio.run(compressor.compress(messages))

        assert recorded.get("ok") is True, "record_event 返回 False——事件未落库"
        # 独立查询验证：事件真在盘上（非仅内存）
        _events = _tracker.get_session_events("e1-session-001")
        _compaction = [e for e in _events if e.get("event_type") == "context_compaction"]
        assert len(_compaction) == 1, f"期望 1 条 context_compaction，实际 {len(_compaction)}"
        _payload = _compaction[0]["event_data"]
        if isinstance(_payload, str):  # 兼容 JSON 字符串存储
            _payload = json.loads(_payload)
        assert _payload["pruned_count"] == 7
        assert _payload["summary"]


class TestRollbackBranchNoWriteback:
    """断言 3：实体保留率 <80% → 回滚分支不写回 + 质量告警落盘 jsonl。"""

    def test_rollback_skips_writeback_and_writes_alert(
        self, verify_on, tmp_path, monkeypatch
    ):
        compressor = _make_compressor()
        messages = _build_messages(400)
        _cb_called = []

        def _cb(event_data: dict) -> None:
            _cb_called.append(event_data)

        compressor.set_writeback_callback(_cb)

        # 质量告警路径指向临时目录（不污染真实 ~/.mimiraether/data/）
        import mimir_constants

        _q_dir = tmp_path / "data"
        monkeypatch.setattr(mimir_constants, "get_mimir_home", lambda: tmp_path)

        # 模拟"压缩后实体丢失"——基类正常返回压缩结果，但验证钩子判定 <80%
        _result = CompressionResult(
            original_count=400, compressed_count=40, summary="lossy summary",
            pruned_tool_count=5, summary_mode="template",
        )
        _post = _build_messages(40, content="compacted-lossy")
        # 强制保留率 0.5 → 触发回滚（实例属性覆盖验证钩子）
        compressor._verify_entity_retention = lambda pre, post: (0.5, ["discussions/a.md"])

        with _mock_base_compress(_post, _result):
            _msgs, _info = asyncio.run(compressor.compress(messages))

        # ① 回滚：返回的是压缩前消息（400 条），不是压缩后的 40 条
        assert len(_msgs) == 400, f"回滚应返回原消息，实际 {len(_msgs)} 条"
        # ② 不写回：回调未被调用
        assert _cb_called == [], "回滚分支不应写回——回调被调用了"
        # ③ 质量告警落盘：compression_quality.jsonl 有告警行
        _q_path = _q_dir / "compression_quality.jsonl"
        assert _q_path.exists(), f"质量告警文件未生成: {_q_path}"
        _lines = _q_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(_lines) >= 1
        _alert = json.loads(_lines[0])
        assert _alert["entity_retention_rate"] == 0.5
        assert _alert["outcome"] == "rollback"


class TestEnvSwitch:
    """env 开关：MIMIR_COMPRESS_WRITEBACK=0 时 core_loop 不注入回调（compressor 侧测试）。"""

    def test_writeback_env_off_means_no_callback_injection(self, monkeypatch):
        """compressor 侧：未 set 回调 = 不写回（env 关闭时 core_loop 不调用 set_writeback_callback）。"""
        monkeypatch.delenv("MIMIR_COMPRESS_WRITEBACK", raising=False)
        compressor = _make_compressor()
        assert compressor._writeback_callback is None  # 未注入
        # 未注入时 compress 成功也不抛异常（_emit_writeback 空回调早退）
        _result = CompressionResult(
            original_count=400, compressed_count=35, summary="s",
            pruned_tool_count=1, summary_mode="template",
        )
        _post = _build_messages(35, content="compacted")
        with _mock_base_compress(_post, _result):
            _msgs, _info = asyncio.run(compressor.compress(_build_messages(400)))
        assert _info.compressed_count == 35
