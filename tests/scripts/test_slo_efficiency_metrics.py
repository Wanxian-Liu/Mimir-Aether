"""SLO 看板效率指标（⑤⑥ 段）行为级用例 —— 2026-09-26「观测第 1 步」。

为什么需要它：这两条指标（单工具轮占比 / 每轮 prompt token）此前**无人量**，
钩子静默退化 5 周不可见。指标本身也会坏（口径写错 ⇒ 读数骗人），
故与仪表同批入版本控制并加行为级用例。

用例都喂**合成日志**（不读生产日志），并且**按今天日期生成时间戳**，
以免时间窗滑动导致用例假红。
"""

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "slo_dashboard.py"

_spec = importlib.util.spec_from_file_location("slo_dashboard_under_test", SCRIPT)
slo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slo)


def _turn(day, n_tools):
    return (
        f"{day} 06:00:00,000 INFO agent.agent_loop: [abcd1234] "
        f"turn 5: api=1.2s, {n_tools} tools, total=2.0s\n"
    )


def _cache(day, prompt):
    return (
        f"{day} 06:00:00,000 INFO agent.callers_mixin: [S2-cache] "
        f"prompt={prompt} hit=100 miss=5 hit_pct=99.9% session= prefix=abcd\n"
    )


@pytest.fixture()
def synth_log(tmp_path, monkeypatch):
    today = datetime.now().strftime("%Y-%m-%d")
    log = tmp_path / "agent.log"
    log.write_text(
        _turn(today, 1)      # 单工具
        + _turn(today, 1)    # 单工具
        + _turn(today, 2)    # 多工具
        + _turn(today, 5)    # 多工具
        + _cache(today, 100)
        + _cache(today, 300)
        + "2026-01-01 00:00:00,000 INFO x: [zzzz] turn 1: api=1.0s, 1 tools, total=1.0s\n"
        + "噪声行：不是 turn 也不是 cache\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(slo, "LOG_GLOB", str(log))
    return log


def test_single_tool_ratio_counts_only_single_tool_turns(synth_log):
    """正控：窗口内 4 轮，单工具 2 轮 ⇒ 50%。"""
    turns, single, ptok = slo._efficiency_stats(days=7)
    assert sum(turns.values()) == 4
    assert sum(single.values()) == 2
    assert len([v for d in ptok for v in ptok[d]]) == 2


def test_multi_tool_only_log_yields_zero_single_ratio(tmp_path, monkeypatch):
    """负控：全是多工具轮 ⇒ 单工具计数必须为 0（证明不是『所有轮都算』）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    log = tmp_path / "only_multi.log"
    log.write_text(_turn(today, 3) + _turn(today, 4), encoding="utf-8")
    monkeypatch.setattr(slo, "LOG_GLOB", str(log))
    turns, single, _ = slo._efficiency_stats(days=7)
    assert sum(turns.values()) == 2
    assert sum(single.values()) == 0


def test_stale_lines_outside_window_excluded(synth_log):
    """窗口外（2026-01-01）的 turn 行不得进入统计。"""
    turns, _, _ = slo._efficiency_stats(days=7)
    for day in turns:
        assert day >= datetime.now().strftime("%Y-%m-%d")[:8]  # 同年同月内


def test_efficiency_section_renders_verdict(synth_log):
    lines = []
    slo.efficiency_section(lines, days=7)
    text = "\n".join(lines)
    assert "## ⑤ 效率指标" in text
    assert "50.0%" in text
    assert "每轮 prompt token" in text
    # 口径固定（nearest-rank 上界）：percentile = sorted[int(n*p/100)]
    # ⇒ 2 个样本时 P50 取上界 300，不是 200。这条断言就是「口径钉」
    # （我首版把期望写成 200 = 我错、代码对 —— 用例与代码必须一起定口径）。
    assert "P50=300" in text
    assert "mean=200" in text


def test_hook_obs_section_missing_file_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # 让 expanduser 指向空目录
    lines = []
    slo.hook_obs_section(lines)
    text = "\n".join(lines)
    assert "## ⑥ 钩子观测" in text
    assert "**无数据**" in text


def test_hook_obs_section_aggregates(tmp_path, monkeypatch):
    ops = tmp_path / ".mimiraether" / "data" / "ops"
    ops.mkdir(parents=True)
    p = ops / "hook_observations.jsonl"
    recs = [
        {"ts": "T1", "hook": "parallel_read_nudge", "decision": "blocked", "reason": "turn_lt_3"},
        {"ts": "T2", "hook": "parallel_read_nudge", "decision": "blocked", "reason": "turn_lt_3"},
        {"ts": "T3", "hook": "pi_delegate_nudge", "decision": "blocked", "reason": "env_disabled"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    lines = []
    slo.hook_obs_section(lines)
    text = "\n".join(lines)
    assert "累计 3 条" in text
    assert "| parallel_read_nudge | blocked | turn_lt_3 | 2 |" in text
    assert "| pi_delegate_nudge | blocked | env_disabled | 1 |" in text
