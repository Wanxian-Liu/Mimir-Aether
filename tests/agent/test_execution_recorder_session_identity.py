"""窗口项 4/5 契约：``session_start`` 自带 ``model`` · raw 会话 id 跨文件唯一。

背景（坑三 HF v2 审计 F1/F4）：
  F1 — session_start 缺 model ⇒ 下游要 join 才知模型（已补）
  F4 — 同一 raw ``session_id`` 落在多个轨迹文件（实测 66/567 文件），
       HF 侧 ``seen`` 只含远端 id ⇒ 跨批同 id 的新会话被**静默丢弃**。
       根治 = 记录器生成唯一 id（不动已发布数据集主键，见 §8 挂账裁决）。

隔离：全部写入 ``tmp_path``（``MIMIR_AETHER_HOME`` 覆写）——**绝不碰生产轨迹目录**。
"""
import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_TRACE_ID", raising=False)
    yield tmp_path


def _rec(**kw):
    from agent.execution_recorder import ExecutionRecorder

    return ExecutionRecorder(**kw)


def test_case1_new_id_is_kept_when_free(_isolated_home):
    r = _rec(task_name="t", session_id="fresh-id")
    assert r._session_id == "fresh-id"
    assert r._file_path.name == "fresh-id.jsonl"
    assert r._file_path.parent.parent == _isolated_home / "trajectories" or (
        "trajectories" in str(r._file_path)
    )


def test_case2_reused_id_is_disambiguated(_isolated_home):
    """同 id 第二次出现 ⇒ 追加短后缀，保证跨文件唯一。"""
    a = _rec(task_name="t", session_id="dup-id")
    b = _rec(task_name="t", session_id="dup-id")
    assert a._session_id == "dup-id"
    assert b._session_id != "dup-id"
    assert b._session_id.startswith("dup-id-")
    assert a._file_path != b._file_path
    assert a._file_path.exists() and b._file_path.exists()

    # 全局唯一性判据（F4 判据原文：raw id 无跨文件复用）
    root = a._file_path.parent.parent
    ids = [p.stem for p in root.rglob("*.jsonl")]
    assert len(ids) == len(set(ids)), "存在跨文件复用的 raw id: %s" % ids


def test_case3_reused_id_across_different_day_dirs(_isolated_home):
    """跨日期目录复用同样被拦（F4 实测 66 个 id 落在 ≥2 个文件，多为跨天）。"""
    from datetime import datetime, timedelta, timezone

    from agent import execution_recorder as er

    root = er._get_trajectory_dir()
    other_day = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
    d = root / other_day
    d.mkdir(parents=True, exist_ok=True)
    (d / "cross-day.jsonl").write_text("{}\n", encoding="utf-8")  # 前几天的同名轨迹

    b = _rec(task_name="t", session_id="cross-day")
    assert b._session_id != "cross-day", "跨日期目录的复用必须被拦"
    assert b._file_path.parent != d, "必须落到今天，不得覆盖历史文件"
    assert not (d / ("%s.jsonl" % b._session_id)).exists()


def test_case4_session_start_has_model(_isolated_home):
    """F1 根治：session_start 行自带非空 model。"""
    r = _rec(task_name="t", session_id="with-model")
    first = json.loads(r._file_path.read_text(encoding="utf-8").splitlines()[0])
    assert first["type"] == "session_start"
    assert first.get("model"), "model 字段不得为空"
    assert first["session_id"] == r._session_id


def test_case5_model_matches_context_usage_source(_isolated_home):
    """验收判据：与 ``last_context_usage.json`` 同源（同读 config.yaml model.default）。"""
    from agent.context_usage_snapshot import _config_default_model

    r = _rec(task_name="t", session_id="model-src")
    first = json.loads(r._file_path.read_text(encoding="utf-8").splitlines()[0])
    expected = str(_config_default_model() or "").strip()
    if expected:
        assert first["model"] == expected


def test_case6_session_start_still_has_provenance(_isolated_home):
    """不回归：X2-a 三字段仍在。"""
    r = _rec(task_name="t", session_id="prov")
    first = json.loads(r._file_path.read_text(encoding="utf-8").splitlines()[0])
    for key in ("trace_id", "trigger_source", "agent_id"):
        assert key in first, "归因字段 %s 丢失" % key


def test_case7_no_production_trajectory_written(_isolated_home):
    """隔离断言：本测试未在生产轨迹目录产生文件。"""
    import os

    prod = Path(os.path.expanduser("~/.mimiraether/trajectories"))
    before = set(p.name for p in prod.rglob("*.jsonl")) if prod.exists() else set()
    r = _rec(task_name="t", session_id="isolation-probe")
    after = set(p.name for p in prod.rglob("*.jsonl")) if prod.exists() else set()
    assert after == before, "测试泄漏到生产轨迹目录"
    assert str(_isolated_home) in str(r._file_path)
