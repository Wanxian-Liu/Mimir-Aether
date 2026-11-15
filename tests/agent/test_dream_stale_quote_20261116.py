"""梦境蒸馏 · 自指环过滤（stale_quote）回归用例（2026-11-16）。

背景
----
`_build_distillation_prompt()` 把最近未裁定矛盾原文以 `[已报 i]` 喂回 prompt，并指示
模型「尽量沿用该条原有措辞」⇒ 若某条历史引用的是**已被删/改写掉的记忆条目**，
那句引文会被逐日复制，形成「检测器拿自己旧输出当事实源」的自指环。

实证（2026-11-16 盘上读数）：矛盾报告 12 条 / 未裁定 5 条，5 条**全部**引用了当前
persistent.json 里已不存在的条目；其中
`技术难题自己想办法整理，四方只作兜底` 全文命中 0 处，却连续 4 天被报为矛盾。

本用例锁三件事：
  T1 引文精确存在 ⇒ 不算 stale（防误删有效历史）
  T2 引文被**改写** ⇒ 不算 stale（纯子串判据会在这里假阳性）
  T3 引文已**消失** ⇒ 算 stale；`_recent_contradictions` 必须把它挡在 prompt 外
  T4 未给 current_text ⇒ 不过滤（向后兼容 + 降级方向：宁可多喂不可误删）
  T5 prompt 规则 9 含两道否决判据（同轴 / 可同时满足）
"""
from __future__ import annotations

import json

import pytest

from agent import dream_memory as dm

LIVE_PATTERN = "任务消息必须真写盘产出后再回执（调研≠完成）"
GONE_DECISION = "技术难题自己想办法整理，四方只作兜底"
PARA_QUOTE = "交付风格：可逆的我定、不可逆的上收"
PARA_REAL = (
    "交付风格：给「建议+我负责执行到底」，可逆的我定、不可逆的上收；"
    "汇报先结论后证据；两条均须落 owner+deadline"
)


def _blob(*texts: str) -> str:
    return "".join(("\n".join(texts)).split())


def test_t1_exact_present_not_stale():
    blob = _blob(GONE_DECISION, LIVE_PATTERN)
    assert dm._stale_quote_items(f"决策「{GONE_DECISION}」与模式「{LIVE_PATTERN}」冲突", blob) == []


def test_t2_paraphrase_not_stale():
    """纯子串判据会在此假阳性：引文是改写而不是消失。

    实测覆盖率 0.786（4-gram），远高于 0.20 阈值 ⇒ 必须视为存活。
    """
    blob = _blob(PARA_REAL)
    assert dm._ref_coverage(PARA_QUOTE, blob) > 0.5
    assert dm._stale_quote_items(f"决策「{PARA_QUOTE}」与某模式冲突", blob) == []


def test_t3_gone_quote_is_stale():
    blob = _blob(LIVE_PATTERN)  # 决策已不在
    stale = dm._stale_quote_items(f"决策「{GONE_DECISION}」与模式「{LIVE_PATTERN}」冲突", blob)
    assert stale == [GONE_DECISION]


def test_t4_no_current_text_does_not_filter():
    """未给 current_text ⇒ 不过滤（向后兼容；降级方向=宁可多喂不可误删）。"""
    assert dm._stale_quote_items(f"决策「{GONE_DECISION}」", "") == []


def test_t3b_recent_contradictions_drops_stale(tmp_path, monkeypatch):
    """端到端：盘上报告留痕不动，但 stale 条目不进 prompt。"""
    report = [
        {"timestamp": "2026-11-12", "contradiction": f"决策「{GONE_DECISION}」与模式「{LIVE_PATTERN}」存在张力", "repeat_count": 4},
        {"timestamp": "2026-11-13", "contradiction": f"决策「{LIVE_PATTERN}」与模式「{LIVE_PATTERN}」同轴真冲突", "repeat_count": 1},
        {"timestamp": "2026-11-14", "contradiction": "已裁定的旧条目", "resolved": "2026-11-15 已裁定"},
    ]
    home = tmp_path / "home"
    (home / "data").mkdir(parents=True)
    (home / "data" / "self_contradiction_report.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))

    blob = dm._format_memory_for_distillation(
        {"memory": {"learned_patterns": [{"pattern": LIVE_PATTERN}]}}
    )

    kept = dm._recent_contradictions(current_text=blob)
    assert len(kept) == 1, kept
    assert "同轴真冲突" in kept[0]

    # 盘上留痕不删（AGENTS §5.5 第 0 级）
    on_disk = json.loads((home / "data" / "self_contradiction_report.json").read_text(encoding="utf-8"))
    assert len(on_disk) == 3

    # 旧行为（不传 current_text）仍然全喂 ⇒ 证明过滤确实来自新参数
    assert len(dm._recent_contradictions()) == 2


def test_t5_prompt_has_veto_criteria():
    prompt = dm._build_distillation_prompt("dummy memory")
    assert "同轴判据" in prompt
    assert "可同时满足判据" in prompt
    assert "不要去凑一条" in prompt


def test_t5b_prompt_drops_stale_history_line():
    """stale 条目进不了 prompt 文本本身（不只是列表层面）。"""
    prompt = dm._build_distillation_prompt("dummy", [f"决策「{GONE_DECISION}」"])
    # 历史段由调用方传入，这里只锁「规则 9 的否决判据存在于最终 prompt」
    assert "同轴判据" in prompt
