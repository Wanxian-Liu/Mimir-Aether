"""D2 RED: dream_memory 写回必须补齐 AKL 字段（2026-10-19）

根因：夜间蒸馏走 `dream_memory._save_persistent()` 自己 json.dump，
绕过 `persistent_store.read_modify_write()` —— 而 `_init_akl_fields` /
`_apply_lifecycle_decay` 只挂在后者里。
实测（2026-10-19）：persistent.json 里 kd/lp **49/49 条无 importance_base**、
`maturity` 全 draft ⇒ 权重每晚被抹平、衰减锚点每晚重置。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent import dream_memory as dm


def test_hydrate_fills_missing_akl_fields():
    data = {"memory": {"key_decisions": [{"decision": "a"}], "learned_patterns": [{"pattern": "b"}]}}
    n = dm._hydrate_akl_fields(data)
    assert n == 2
    for key in ("key_decisions", "learned_patterns"):
        e = data["memory"][key][0]
        assert "importance_base" in e, key
        assert "maturity" in e, key
        assert "last_access" in e, key


def test_hydrate_preserves_existing_importance():
    data = {"memory": {"key_decisions": [{"decision": "a", "importance": 90}], "learned_patterns": []}}
    dm._hydrate_akl_fields(data)
    assert data["memory"]["key_decisions"][0]["importance"] == 90
    assert data["memory"]["key_decisions"][0]["importance_base"] == 90


def test_hydrate_is_idempotent_same_day():
    data = {"memory": {"key_decisions": [{"decision": "a", "importance": 90}], "learned_patterns": []}}
    dm._hydrate_akl_fields(data)
    first = data["memory"]["key_decisions"][0]["importance"]
    dm._hydrate_akl_fields(data)
    assert data["memory"]["key_decisions"][0]["importance"] == first


def test_save_persistent_writes_akl_fields(tmp_path):
    p = tmp_path / "persistent.json"
    data = {"memory": {"key_decisions": [{"decision": "x"}], "learned_patterns": [{"pattern": "y"}]}}
    assert dm._save_persistent(str(p), data) is True
    written = json.loads(p.read_text())
    for key in ("key_decisions", "learned_patterns"):
        assert "importance_base" in written["memory"][key][0], key


def test_hydrate_no_memory_key_is_noop():
    assert dm._hydrate_akl_fields({}) == 0
    assert dm._hydrate_akl_fields({"memory": None}) == 0
