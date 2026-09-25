"""记忆注入层接线守卫（2026-09-26）。

钉住的缺口：``tools/memory_tool.MemoryStore.format_for_system_prompt`` 早已实现，
但**全仓零调用者** ⇒ 手写 MEMORY.md（138 条 / 37,006 字符）从未进入系统提示，
真正到场的只有 2,000 字符的 cross-session 切片（实测 ≈430 tokens）。

本文件是**行为级**断言（不是「源码含某串」）：真实构建系统提示，看记忆块是否
到场、是否受上限约束、kill switch 是否生效。
"""

from __future__ import annotations

import pytest

MODEL = "deepseek/deepseek-flash"
MEM_FACT = "测试事实-唯一哨兵串-ALPHA-9173"
USER_FACT = "测试画像-唯一哨兵串-BETA-4421"


@pytest.fixture
def iso(tmp_path, monkeypatch):
    home = str(tmp_path / "mimir_home")
    monkeypatch.setenv("MIMIR_AETHER_HOME", home)
    monkeypatch.setenv("MIMIRAETHER_HOME", home)
    import tools.memory_tool as mt

    mt.reset_memory_store_for_test()
    # 外部 ML 组件不在仓内 ⇒ 固定为 None，避免测试依赖环境
    monkeypatch.setattr(mt, "KnowledgeDeduplicator", None)
    monkeypatch.setattr(mt, "ImportanceScorer", None)
    yield mt, home
    mt.reset_memory_store_for_test()


def _write(mt, target: str, entries) -> None:
    d = mt.get_memory_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / ("MEMORY.md" if target == "memory" else "USER.md")).write_text(
        mt.ENTRY_DELIMITER.join(entries), encoding="utf-8"
    )


def _reload(mt):
    mt.reset_memory_store_for_test()
    store = mt.get_memory_store()
    store.load_from_disk()
    return store


def test_memory_block_reaches_system_prompt(iso):
    """主缺口：有记忆条目时，记忆块必须**真的**出现在系统提示里。"""
    mt, _ = iso
    _write(mt, "memory", [MEM_FACT])
    _write(mt, "user", [USER_FACT])
    _reload(mt)

    from agent.prompt_builder import build_system_prompt, build_system_prompt_parts

    flat = build_system_prompt(MODEL, include_context=True)
    assert MEM_FACT in flat, "MEMORY.md 条目未进入系统提示（接线退化）"
    assert USER_FACT in flat, "USER.md 条目未进入系统提示（接线退化）"
    assert "MEMORY (your personal notes)" in flat
    assert "USER PROFILE (who the user is)" in flat

    parts = build_system_prompt_parts(MODEL, include_context=True)
    assert MEM_FACT in parts["volatile"], "记忆块必须落在 volatile 分区（冻结语义）"
    assert MEM_FACT not in parts["stable"]


def test_no_entries_no_header(iso):
    """空记忆 ⇒ 不注入空块（避免常态噪声）。"""
    mt, _ = iso
    _reload(mt)
    from agent.prompt_builder import _build_memory_block

    assert _build_memory_block() == ""


def test_kill_switch_disables_injection(iso, monkeypatch):
    mt, _ = iso
    _write(mt, "memory", [MEM_FACT])
    _reload(mt)
    monkeypatch.setenv("MIMIR_MEMORY_IN_PROMPT", "0")
    from agent.prompt_builder import _build_memory_block

    assert _build_memory_block() == ""


def test_default_limits_match_hermes_chain():
    """链上限：与 Hermes 现网一致（8,000 / 4,000 字符），且不再是无约束的 55,000。"""
    import tools.memory_tool as mt

    store = mt.MemoryStore()
    assert store.memory_char_limit == 8000
    assert store.user_char_limit == 4000


def test_stats_reports_under_limit_and_counts(iso):
    mt, _ = iso
    _write(mt, "memory", [MEM_FACT])
    _write(mt, "user", [USER_FACT])
    _reload(mt)
    from agent.prompt_builder import memory_injection_stats

    st = memory_injection_stats()
    assert st["memory_chars"] > 0 and st["user_chars"] > 0
    assert st["memory_limit"] == 8000 and st["user_limit"] == 4000
    assert st["over_limit"] is False
    assert st["total_chars"] == st["memory_chars"] + st["user_chars"]


def test_stats_flags_over_limit(iso):
    """超上限必须被量出来（写侧会拒绝新增，但存量超限要可见）。"""
    mt, _ = iso
    _write(mt, "memory", ["X" * 9000])
    _reload(mt)
    from agent.prompt_builder import memory_injection_stats

    st = memory_injection_stats()
    assert st["memory_chars"] > st["memory_limit"]
    assert st["over_limit"] is True


def test_store_failure_degrades_without_raising(monkeypatch):
    """注入层失败不得拖垮提示组装，也不得伪装成「有内容」。"""
    import tools.memory_tool as mt

    def _boom():
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(mt, "get_memory_store", _boom)
    from agent.prompt_builder import _build_memory_block, memory_injection_stats

    assert _build_memory_block() == ""
    assert memory_injection_stats()["total_chars"] == 0
