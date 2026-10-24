"""晋升制（⑤）正控 / 负控 / 反假绿臂 —— 2026-10-24 刘哥批「方式二 + 晋升制」。

判据语义（AGENTS §9 档位 ④ 两向）：
- 正控：达门条目必须被晋升（maturity=promoted + promoted_at 落盘）
- 负控：全 draft + access_count=0（无任何使用证据）⇒ 晋升计数必须 = 0
- 反假绿臂：把写回段换成「无条件 setdefault('maturity','promoted')」时，负控必须变红
  —— 这一臂证明负控不是恒过的装饰（delta≠0）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent import dream_memory as dm  # noqa: E402


NOW = datetime.now(timezone.utc).isoformat()
OLD = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()


def _draft(n: int, access: int = 0, importance: int = 40, last_access: str = OLD):
    return [
        {
            "decision": f"d{i}",
            "importance": importance,
            "maturity": "draft",
            "access_count": access,
            "last_access": last_access,
            "created_at": OLD,
        }
        for i in range(n)
    ]


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(dm, "_mimir_home", lambda: str(tmp_path))
    (tmp_path / "data").mkdir()
    return tmp_path


def test_positive_control_promotes_used_items():
    items = _draft(3, access=2)
    promoted, total = dm._apply_promotion_pass(items, NOW)
    assert total == 3
    assert promoted > 0, "正控失败：有使用证据的条目必须被晋升"
    assert all(i["maturity"] == "promoted" for i in items)
    assert all(i.get("promoted_at") == NOW for i in items)


def test_negative_control_no_usage_stays_draft():
    items = _draft(49, access=0, importance=40, last_access=OLD)
    promoted, total = dm._apply_promotion_pass(items, NOW)
    assert total == 49
    assert promoted == 0, "负控失败：无使用证据的条目不得晋升"
    assert all(i["maturity"] == "draft" for i in items)
    assert all("promoted_at" not in i for i in items)


def test_negative_control_detects_unconditional_green(monkeypatch):
    """反假绿臂：把晋升门换成无条件写法 ⇒ 上面那条负控必须变红。"""

    def fake(item, now_iso):
        item.setdefault("maturity", "promoted")
        item.setdefault("promoted_at", now_iso)
        return True

    monkeypatch.setattr(dm, "_apply_promotion", fake)
    items = _draft(49, access=0)
    promoted, _ = dm._apply_promotion_pass(items, NOW)
    assert promoted == 49, "假绿臂应全绿——否则说明负控测的不是这件事"


def test_archive_evicted_is_grep_able(home):
    dropped = _draft(2, access=0)
    n = dm._archive_evicted("key_decisions", dropped, "truncation")
    assert n == 2
    path = Path(dm._archive_path())
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    payload = json.loads(body)
    assert len(payload) == 2
    assert payload[0]["reason"] == "truncation"
    assert "d0" in body and "d1" in body


def test_archive_appends_and_keeps_kind(home):
    dm._archive_evicted("key_decisions", _draft(1, access=0), "truncation")
    dm._archive_evicted("behavioral_constraints", ["你不应该在未验证量具存活时引用指标"], "constraint_cap")
    payload = json.loads(Path(dm._archive_path()).read_text(encoding="utf-8"))
    assert [p["kind"] for p in payload] == ["key_decisions", "behavioral_constraints"]
    assert "量具存活" in payload[1]["text"]


def test_clear_failure_record_on_success(home):
    p = Path(dm._failure_record_path())
    p.write_text('{"stage": "save"}', encoding="utf-8")
    assert dm._clear_failure_record() is True
    assert not p.exists()
    assert dm._clear_failure_record() is False  # 幂等：再删一次不报错


def test_usage_evidence_takes_max_not_sum():
    assert dm._usage_evidence({"access_count": 3, "retrieval_hits": 1}) == 3
    assert dm._usage_evidence({"access_count": "x", "retrieval_hits": 2}) == 2
    assert dm._usage_evidence({}) == 0
