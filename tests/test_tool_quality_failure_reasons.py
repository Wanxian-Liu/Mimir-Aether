"""P3 失败原因留痕（卡2-②）的回归闸 —— 2026-11-08。

背景：``tool_quality`` 表原本只有 ``success_count``，失败原因无处落盘 ⇒
``skill_manage`` 76 次失败（330/254）无法拆解。本闸锁三件事：

1. ``classify_failure`` 是纯函数且**两向**可分（空消息 → unknown，命中关键词 → 对应类）；
2. ``ToolQualityRecord.add_execution`` 在失败时**累加** reason 计数，成功时不动；
3. 旧库（无 failure_reasons 列）能被 ``ToolQualityStore`` 自动迁移，且 round-trip 不丢字段。

第 3 条是「新旧库列序错位」的防线：ALTER TABLE 把新列追加在末尾，新建库则按
_SCHEMA 顺序 —— 位置索引会在两种库之间错位（本文件用临时库显式造出旧 schema）。
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tool_quality import (  # noqa: E402
    ExecutionRecord,
    ToolQualityRecord,
    ToolQualityStore,
    classify_failure,
)

# ── 1. classify_failure：两向 ──────────────────────────────────────────────


def test_classify_failure_maps_known_reasons():
    cases = {
        "Skill not found: mimiraether-self-audi": "not_found",
        "No such file or directory: /nope": "not_found",
        "Read timed out after 30s": "timeout",
        "Blocked by path whitelist: /etc/passwd": "blocked_by_policy",
        "Permission denied": "permission",
        "rate limit exceeded (429)": "rate_limit",
        "Connection refused": "network",
        "invalid argument: model": "invalid_args",
    }
    for msg, expected in cases.items():
        assert classify_failure(msg) == expected, (msg, classify_failure(msg))


def test_classify_failure_unknown_vs_other():
    # 负控：没有消息 ⇒ unknown（失败留痕但原因不明，不许被吞成 other）
    assert classify_failure("") == "unknown"
    assert classify_failure(None) == "unknown"
    # 有消息但匹配不上任何类 ⇒ other
    assert classify_failure("something odd happened") == "other"


def test_classify_failure_class_set_is_closed():
    from agent.tool_quality import FAILURE_REASON_CLASSES

    for msg in ("", "Skill not found", "weird"):
        assert classify_failure(msg) in FAILURE_REASON_CLASSES


# ── 2. add_execution 计数 ─────────────────────────────────────────────────


def test_add_execution_counts_reason_on_failure_only():
    rec = ToolQualityRecord(tool_key="t", tool_name="t")
    rec.add_execution(ExecutionRecord(timestamp="1", success=True, duration_ms=1.0))
    assert rec.failure_reasons == {}

    rec.add_execution(ExecutionRecord(
        timestamp="2", success=False, duration_ms=1.0,
        error_message="Skill not found: x"))
    rec.add_execution(ExecutionRecord(
        timestamp="3", success=False, duration_ms=1.0,
        error_message="Skill not found: y"))
    assert rec.failure_reasons == {"not_found": 2}


# ── 3. 旧库迁移 + round-trip（列序错位防线）────────────────────────────────

_OLD_SCHEMA = """
CREATE TABLE tool_quality (
    tool_key   TEXT PRIMARY KEY,
    tool_name  TEXT NOT NULL,
    total_calls INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    total_duration_ms REAL DEFAULT 0.0,
    recent_executions TEXT DEFAULT '[]',
    llm_flagged_count INTEGER DEFAULT 0,
    first_seen  TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""


def _make_old_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    con.executescript(_OLD_SCHEMA)
    con.execute(
        "INSERT INTO tool_quality VALUES (?,?,?,?,?,?,?,?,?)",
        ("legacy", "legacy", 10, 7, 100.0, json.dumps([]), 0,
         "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
    )
    con.commit()
    con.close()


def test_store_migrates_old_db_and_roundtrips(tmp_path):
    db = tmp_path / "legacy.db"
    _make_old_db(db)

    store = ToolQualityStore(db_path=db)
    cols = {r[1] for r in sqlite3.connect(str(db)).execute("PRAGMA table_info(tool_quality)")}
    assert "failure_reasons" in cols, cols

    loaded = store.load_all()
    assert loaded["legacy"].total_calls == 10          # 旧行没被新列序错位读坏
    assert loaded["legacy"].success_count == 7
    assert loaded["legacy"].first_seen == "2026-01-01T00:00:00+00:00"
    assert loaded["legacy"].failure_reasons == {}

    loaded["legacy"].add_execution(ExecutionRecord(
        timestamp="9", success=False, duration_ms=1.0, error_message="Connection refused"))
    store.save(loaded["legacy"])

    again = ToolQualityStore(db_path=db).load_all()["legacy"]
    assert again.failure_reasons == {"network": 1}
    assert again.total_calls == 11 and again.success_count == 7
    assert again.first_seen == "2026-01-01T00:00:00+00:00"
