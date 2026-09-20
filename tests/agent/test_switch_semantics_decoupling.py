"""IQ 批2 · 开关语义组拆分：量具组（record-only）与执行器组（可写）必须可独立开关。

实证背景：2026-08-16 13:41 一次运维把两组共 4 个键一起改成 0 ⇒ 采集器停摆 5 周，
「零事件」被读成「零失败」（量具坏掉静默表现为「没有反馈」）。

臂设计：
* A1 分组契约：两组互斥且并集 = 文档口径的 5 键
* A2 正控（解耦成立）：量具开 + 执行器组全 0 ⇒ 事件仍落盘
* A3 负控（无交叉污染）：量具关 + 执行器组全开 ⇒ 不落任何事件
* A4 快照面：基线脚本输出分量具/执行器两组（旧 env 键保留）
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from agent import feedback_collector as fc

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts" / "iq_p3_evolution_ok_baseline.py"

DOC_KEYS = {
    "MIMIR_FEEDBACK_COLLECTOR",
    "MIMIR_AUTO_ANALYSIS",
    "MIMIR_AUTO_EVOLVE",
    "MIMIR_AUTO_TUNER",
    "MIMIR_AUTO_1C_POLICY",
}


def _set_executors(monkeypatch, value: str) -> None:
    for key in fc.EXECUTOR_ENV_KEYS:
        monkeypatch.setenv(key, value)


def test_a1_groups_are_disjoint_and_complete():
    assert fc.switch_semantics()["disjoint"] is True
    assert not (set(fc.INSTRUMENT_ENV_KEYS) & set(fc.EXECUTOR_ENV_KEYS))
    assert set(fc.INSTRUMENT_ENV_KEYS) | set(fc.EXECUTOR_ENV_KEYS) == DOC_KEYS
    assert fc.switch_semantics()["instrument"]["policy"] == "常开"


def test_a2_instrument_on_executors_off_still_records(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_FEEDBACK_COLLECTOR", "1")
    _set_executors(monkeypatch, "0")
    fc.reset_feedback_collector_state()

    fc.record_tool_outcome_feedback("read_file", success=False, error_message="ENOENT")

    log = tmp_path / "data" / "feedback_events.jsonl"
    assert log.is_file(), "量具组开启即应落盘，不得被执行器组关闭连坐"
    row = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["event_type"] == "tool_failure"


def test_a3_instrument_off_executors_on_records_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_FEEDBACK_COLLECTOR", "0")
    _set_executors(monkeypatch, "1")
    fc.reset_feedback_collector_state()

    fc.record_tool_outcome_feedback("read_file", success=False, error_message="ENOENT")

    assert not (tmp_path / "data" / "feedback_events.jsonl").is_file()
    assert fc.recent_feedback_events() == []


def _load_baseline():
    spec = importlib.util.spec_from_file_location("iq_p3_baseline_probe", BASELINE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a4_baseline_snapshot_splits_groups(tmp_path):
    mod = _load_baseline()
    cfg = tmp_path / ("." + "env")
    cfg.write_text(
        "\n".join(
            [
                "MIMIR_FEEDBACK_COLLECTOR=1",
                "MIMIR_AUTO_ANALYSIS=0",
                "MIMIR_AUTO_EVOLVE=0",
                "MIMIR_AUTO_TUNER=0",
                "MIMIR_AUTO_1C_POLICY=0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    payload = mod.build_baseline(home=tmp_path, days=1.0)

    assert payload["env"]["MIMIR_FEEDBACK_COLLECTOR"] == "1"  # 旧键向后兼容
    groups = payload["env_groups"]
    assert set(groups["instrument"]) == {"MIMIR_FEEDBACK_COLLECTOR"}
    assert set(groups["executor"]) == set(fc.EXECUTOR_ENV_KEYS)
    assert not set(groups["instrument"]) & set(groups["executor"])
