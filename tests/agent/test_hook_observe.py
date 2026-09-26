"""钩子观测层行为级用例（2026-09-26 · 「观测第 1 步」）。

覆盖两条运行时钩子（parallel-read nudge / PI auto-delegate）的**门控原因落盘**：
  * 门未过 ⇒ decision=blocked + 精确 reason
  * 门全过 ⇒ decision=triggered
  * 观测**不改变**钩子返回值（同参两次调用结果一致）
  * env 关（MIMIR_HOOK_OBSERVE=0）⇒ 零写盘（负控：证明「有落盘」不是环境自带）
  * 观测自身异常不得外溢（不可写路径 ⇒ 静默）

隔离：用 MIMIR_HOOK_OBS_PATH 指向 tmp，绝不碰生产的 data/ops/hook_observations.jsonl。
"""

import json

import pytest

from agent import hook_observe
from agent.conversation_nudges import maybe_parallel_read_nudge
from agent.pi_trigger import maybe_pi_delegate_nudge


@pytest.fixture()
def obs_file(tmp_path, monkeypatch):
    path = tmp_path / "hook_observations.jsonl"
    monkeypatch.setenv(hook_observe.OBS_ENV_PATH, str(path))
    monkeypatch.setenv(hook_observe.OBS_ENV_ENABLE, "1")
    hook_observe.reset_path_cache()
    yield path
    hook_observe.reset_path_cache()


def _rows(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- observe 本体


def test_observe_writes_one_jsonl_line(obs_file):
    hook_observe.observe("unit_hook", "blocked", "some_reason", turn=3, tools=1)
    rows = _rows(obs_file)
    assert len(rows) == 1
    assert rows[0]["hook"] == "unit_hook"
    assert rows[0]["decision"] == "blocked"
    assert rows[0]["reason"] == "some_reason"
    assert rows[0]["turn"] == 3 and rows[0]["tools"] == 1
    assert "ts" in rows[0] and "pid" in rows[0]


def test_observe_disabled_writes_nothing(obs_file, monkeypatch):
    """负控：关掉开关必须零写盘 —— 证明上面那条不是『总是写』。"""
    monkeypatch.setenv(hook_observe.OBS_ENV_ENABLE, "0")
    hook_observe.observe("unit_hook", "triggered", "injected")
    assert _rows(obs_file) == []


def test_observe_never_raises_on_bad_path(tmp_path, monkeypatch):
    monkeypatch.setenv(hook_observe.OBS_ENV_PATH, "/proc/definitely/not/writable/x.jsonl")
    hook_observe.reset_path_cache()
    try:
        hook_observe.observe("unit_hook", "blocked", "whatever")  # 不得抛
    finally:
        hook_observe.reset_path_cache()


# ------------------------------------------------- parallel-read nudge 四态


@pytest.mark.parametrize(
    "turn,tools,expect_none,reason",
    [
        (0, 0, True, "turn_lt_3"),
        (5, 1, True, "tools_lt_2"),
        (5, 4, False, "injected"),
    ],
)
def test_parallel_read_nudge_reasons(obs_file, monkeypatch, turn, tools, expect_none, reason):
    monkeypatch.delenv("MIMIR_PARALLEL_READ_NUDGE", raising=False)
    out = maybe_parallel_read_nudge(turn, tools)
    assert (out is None) is expect_none
    rows = _rows(obs_file)
    assert len(rows) == 1, rows
    assert rows[0]["hook"] == "parallel_read_nudge"
    assert rows[0]["reason"] == reason
    assert rows[0]["decision"] == ("blocked" if expect_none else "triggered")


def test_parallel_read_nudge_env_off_reason(obs_file, monkeypatch):
    monkeypatch.setenv("MIMIR_PARALLEL_READ_NUDGE", "0")
    assert maybe_parallel_read_nudge(9, 9) is None
    assert _rows(obs_file)[0]["reason"] == "env_disabled"


def test_parallel_read_nudge_return_unchanged_by_observation(obs_file, monkeypatch):
    """观测是纯增量：开关观测前后，返回值必须一致。"""
    monkeypatch.delenv("MIMIR_PARALLEL_READ_NUDGE", raising=False)
    with_obs = maybe_parallel_read_nudge(4, 3)
    monkeypatch.setenv(hook_observe.OBS_ENV_ENABLE, "0")
    without_obs = maybe_parallel_read_nudge(4, 3)
    assert with_obs == without_obs
    assert with_obs is not None


# --------------------------------------------------- PI auto-delegate 门控原因


def test_pi_nudge_env_disabled_reason(obs_file, monkeypatch):
    monkeypatch.setenv("MIMIR_DELEGATE_ENABLE", "0")
    assert maybe_pi_delegate_nudge([{"role": "user", "content": "帮我审计这个仓库"}]) is None
    assert _rows(obs_file)[0]["reason"] == "env_disabled"


def test_pi_nudge_short_task_records_est_below_min(obs_file, monkeypatch):
    """短任务 ⇒ est < min_turns ⇒ 必须留下 est_below_min（而不是静默 None）。"""
    monkeypatch.delenv("MIMIR_DELEGATE_ENABLE", raising=False)
    monkeypatch.setenv("MIMIR_PI_MIN_TURNS", "8")
    assert maybe_pi_delegate_nudge([{"role": "user", "content": "你好"}]) is None
    row = _rows(obs_file)[0]
    assert row["hook"] == "pi_delegate_nudge"
    assert row["reason"] == "est_below_min"
    assert row["min_turns"] == 8


def test_pi_nudge_no_task_text_reason(obs_file, monkeypatch):
    monkeypatch.delenv("MIMIR_DELEGATE_ENABLE", raising=False)
    assert maybe_pi_delegate_nudge([{"role": "assistant", "content": "hi"}]) is None
    assert _rows(obs_file)[0]["reason"] == "no_task_text"
