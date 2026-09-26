"""E3 步1 · 工具输出离场：行为级回归。

背景（2026-09-26 实测）：tools/tool_result_storage.py 自 05-16 存在并已接线
agent_loop.py 两处，但调用点显式传 ``config=self.budget_config``（默认 None）
⇒ 覆盖签名默认值 ⇒ ``None.resolve_threshold`` 抛 AttributeError ⇒ 被
``except Exception: pass`` 吞掉 ⇒ **该机制自上线起一次都没跑过**（0 日志/0 产物/0 测试）。

本文件锁三件事：
  ① 病形态（config=None）不得再静默失效；
  ② 离场必须**保全文**（落盘内容逐字节等于原文）——否则是数据丢失而非省 token；
  ③ 每个决策点都要留观测行（含不触发的原因），防「静默失效」复发。
"""

import logging
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools import tool_result_storage as trs  # noqa: E402


BIG = "行内容 " * 2000  # ≈ 8000 字符，远超默认 4000 阈值


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """隔离：离场目录指到 tmp；清掉开关/阈值，保证各臂从默认态起跑。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_TOOL_OFFLOAD", raising=False)
    monkeypatch.delenv("MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS", raising=False)
    trs._last_prune_at[0] = 0.0
    yield


# ─────────────────── ① 主路径：离场 + 全文保真 ───────────────────

def test_offloads_and_preserves_full_text(tmp_path):
    out = trs.maybe_persist_tool_result(
        content=BIG, tool_name="execute_code", tool_use_id="call_aaa", env=None,
    )
    assert out != BIG, "超阈值结果必须被替换为预览块"
    assert len(out) < len(BIG) / 2, "上下文占用必须显著下降"
    assert trs.PERSISTED_OUTPUT_TAG in out

    files = list((tmp_path / "data" / "tool_offload").rglob("*.txt"))
    assert len(files) == 1, "必须落盘恰好一个文件"
    assert files[0].read_text(encoding="utf-8") == BIG, "落盘内容必须逐字节等于原文"
    assert str(files[0]) in out, "预览块必须给出可回读路径"


def test_preview_keeps_head_and_tail():
    tail_sentinel = "TAIL_SENTINEL_结论行"
    content = ("头" * 3000) + ("中" * 3000) + tail_sentinel
    out = trs.maybe_persist_tool_result(
        content=content, tool_name="execute_code", tool_use_id="call_tail", env=None,
    )
    assert out.startswith(trs.PERSISTED_OUTPUT_TAG + "\n"), "应保持既有消息结构"
    assert tail_sentinel in out, "尾部常含结论（测试汇总/报错行），必须保留"


# ─────────────────── ② 病形态回归（本文件存在的首要理由） ───────────────────

def test_config_none_no_longer_breaks():
    out = trs.maybe_persist_tool_result(
        content=BIG, tool_name="execute_code", tool_use_id="call_none",
        env=None, config=None,          # ← 复刻生产的调用形态
    )
    assert trs.PERSISTED_OUTPUT_TAG in out, "config=None 也必须正常离场（曾抛异常被吞）"


def test_legacy_form_would_have_raised():
    """对照臂：钉住旧失效形态，保证上面的回归臂有鉴别力。"""
    with pytest.raises(AttributeError):
        None.resolve_threshold("execute_code")   # type: ignore[union-attr]
    out = trs.maybe_persist_tool_result(
        content=BIG, tool_name="execute_code", tool_use_id="call_cmp", env=None,
    )
    assert out != BIG, "同一输入在新形态下必须离场（两臂读数可比）"


# ─────────────────── ③ 开关 / 阈值 / 钉子 ───────────────────

def test_disabled_by_env_returns_original(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_TOOL_OFFLOAD", "0")
    out = trs.maybe_persist_tool_result(
        content=BIG, tool_name="execute_code", tool_use_id="call_off", env=None,
    )
    assert out == BIG, "回滚开关必须立即恢复原行为"
    assert not list((tmp_path / "data" / "tool_offload").rglob("*.txt")), "关掉后不得落盘"


def test_below_threshold_untouched(tmp_path):
    small = "小结果" * 10
    out = trs.maybe_persist_tool_result(
        content=small, tool_name="execute_code", tool_use_id="call_small", env=None,
    )
    assert out == small
    assert not list((tmp_path / "data" / "tool_offload").rglob("*.txt"))


def test_pinned_tool_never_offloaded(tmp_path):
    """read_file 被 PINNED 为 inf（防 persist→read→persist 环），不得被本层打破。"""
    out = trs.maybe_persist_tool_result(
        content=BIG, tool_name="read_file", tool_use_id="call_read", env=None,
    )
    assert out == BIG
    assert not list((tmp_path / "data" / "tool_offload").rglob("*.txt"))


def test_threshold_env_tightens_but_never_loosens(monkeypatch):
    mid = "x" * 2000
    # 收紧：2000 > 500 ⇒ 离场
    monkeypatch.setenv("MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS", "500")
    assert trs.maybe_persist_tool_result(
        content=mid, tool_name="execute_code", tool_use_id="call_t1", env=None,
    ) != mid
    # 放宽：env 大于注册阈值时不得放宽（否则等于关掉了保护）
    monkeypatch.setenv("MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS", str(10 ** 9))
    assert trs.maybe_persist_tool_result(
        content=mid, tool_name="execute_code", tool_use_id="call_t2", env=None,
    ) == mid


def test_invalid_threshold_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MIMIR_TOOL_OFFLOAD_THRESHOLD_CHARS", "not-a-number")
    assert trs._threshold_override() == trs._OFFLOAD_DEFAULT_THRESHOLD


def test_default_threshold_is_actually_wired():
    """防死常量：注册阈值 100000，若默认 4000 没接上，8K 结果就永不触发。"""
    assert trs._threshold_override() == trs._OFFLOAD_DEFAULT_THRESHOLD
    assert trs.maybe_persist_tool_result(
        content="y" * 8000, tool_name="execute_code", tool_use_id="call_def", env=None,
    ) != "y" * 8000


# ─────────────────── ④ fail-open：不得静默丢数据 ───────────────────

def test_write_failure_fails_open(monkeypatch, caplog):
    monkeypatch.setattr(trs, "_write_local", lambda *a, **k: None)
    with caplog.at_level(logging.WARNING):
        out = trs.maybe_persist_tool_result(
            content=BIG, tool_name="execute_code", tool_use_id="call_fail", env=None,
        )
    assert out == BIG, "落盘失败时必须保留原文（宁可占上下文，不可丢数据）"
    assert any("no_backend" in r.message for r in caplog.records), "失败必须留痕"


# ─────────────────── ⑤ 观测：每个决策点都要能归因 ───────────────────

def test_observation_line_for_below_threshold(caplog):
    with caplog.at_level(logging.INFO):
        trs.maybe_persist_tool_result(
            content="tiny", tool_name="execute_code", tool_use_id="call_obs1", env=None,
        )
    assert any("[TOOL-OFFLOAD]" in r.message and "below_threshold" in r.message
               for r in caplog.records)


def test_observation_line_for_offload(caplog):
    with caplog.at_level(logging.INFO):
        trs.maybe_persist_tool_result(
            content=BIG, tool_name="execute_code", tool_use_id="call_obs2", env=None,
        )
    assert any("[TOOL-OFFLOAD]" in r.message and "decision=offloaded" in r.message
               for r in caplog.records)


def test_observation_line_for_disabled(monkeypatch, caplog):
    monkeypatch.setenv("MIMIR_TOOL_OFFLOAD", "0")
    with caplog.at_level(logging.INFO):
        trs.maybe_persist_tool_result(
            content=BIG, tool_name="execute_code", tool_use_id="call_obs3", env=None,
        )
    assert any("decision=disabled" in r.message for r in caplog.records)


# ─────────────────── ⑥ 接线守卫（防「助手在但没人叫」复发） ───────────────────

def test_hook_still_wired_at_both_call_sites():
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "agent" / "agent_loop.py").read_text(encoding="utf-8")
    assert src.count("maybe_persist_tool_result(") == 2, "两处调用点都必须保留"


def test_call_sites_do_not_swallow_silently():
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "agent" / "agent_loop.py").read_text(encoding="utf-8")
    assert "TOOL-OFFLOAD] hook failed" in src, "调用点必须记录失败（静默吞=上一个 bug 的成因）"
