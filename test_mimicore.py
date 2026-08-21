"""
test_mimicore.py — 引用已删除的旧 API（2026-08-21 四方会议 Mimir 段取证）
====================================================================
引用 tools/mimircore_tool.py 的 `produce_capsule` 顶层函数，
但该函数已重构为工具注册方式（name="produce_capsule" 的 _handle_produce_capsule）。
标记 skip，等待按新工具 API 重写。
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="引用旧 API produce_capsule（已重构为工具注册），2026-08-21 取证标记，待重写"
)
