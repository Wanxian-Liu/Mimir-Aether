"""Gate A3 / WA-A06: search_first_audit script."""

from __future__ import annotations

from scripts.search_first_audit import audit_session, exclude_reason, run_audit


def test_exclude_reason_filters_false_positives():
    assert exclude_reason("继续离席清单") == "task_continuation"
    assert exclude_reason("已经 new 了，现在是新对话，可以继续了") == "fresh_session_continue"
    assert exclude_reason("深度理解后写入 Bridge") == "bridge_write_task"
    assert exclude_reason("┌──────┐\n│ Agent │") == "user_paste_block"
    assert exclude_reason("世界模型是哲学和物理学") == "topic_discussion_no_recall_ask"
    assert exclude_reason("查历史 IR-20260520") == ""


def test_run_audit_returns_rows(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    path = sessions / "s1.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"role":"user","content":"查历史 IR-20260520"}',
                '{"role":"assistant","content":"找到了 3 个 session 命中 session_search"}',
                '{"role":"user","content":"继续离席清单"}',
                '{"role":"assistant","content":"ok"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.search_first_audit.get_mimir_home",
        lambda: tmp_path,
    )
    out = run_audit(sessions_dir=sessions, limit=10)
    assert out["ok"] is True
    assert out["recall_candidates_total"] == 2
    assert out["filtered_recall_candidates_total"] == 1
    assert out["filtered_violation_rate"] == 0.0


def test_audit_session_marks_exclusions(tmp_path):
    path = tmp_path / "mix.jsonl"
    path.write_text(
        '{"role":"user","content":"继续入库并检查"}\n',
        encoding="utf-8",
    )
    rows = audit_session(path)
    assert len(rows) == 1
    assert rows[0].exclude_reason == "task_continuation"
    assert not rows[0].filtered_in_scope
