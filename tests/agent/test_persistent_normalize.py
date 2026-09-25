"""RS20 治本回归臂：persistent.json 写盘前规范化（2026-09-26）。

被防的**具体事故**（不是假想）：

    03:10:34  瘦身写入 → persistent.json = 41,058 B
    03:17:19  被系统自己回滚 → 82,565 B（废弃字段全回来）
    03:21:21  审计发现，事后重放才恢复

根因：``CrossSessionMemory.save()`` 在 run 收尾用**进程内快照**整文件重写，而该
实例的加载时刻早于瘦身时刻 ⇒ 旧内存副本复活废弃字段。

**本轮之前缺的正是 B 组那条臂**：把「内存含废弃字段 + 磁盘已瘦身」这个组合喂给
真实写入路径，断言写盘后仍为瘦身态。A1-A3 只证明「字段被删了」，不证明
「删掉之后不会被写回来」。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent import persistent_store  # noqa: E402
from agent.persistent_normalize import (  # noqa: E402
    DORMANT_AT_DATE_CHARS,
    MAX_DORMANT_SUMMARY_CHARS,
    DEPRECATED_FIELDS,
    normalize,
    normalize_and_log,
)

# ── 夹具 ────────────────────────────────────────────────────────────────────


def _dirty_state() -> dict:
    """旧内存副本（含全部四类废弃字段）+ 合法字段。"""
    return {
        "version": "1.4",
        "memory": {"key_decisions": [], "learned_patterns": [], "active_projects": []},
        "progress": {
            "current_objective": "RS20",
            "completed_milestones": ["m1", "m2"],
            "milestone_relations": {f"n{i}": {"to": f"n{i + 1}"} for i in range(84)},
        },
        "dormant_skills": {
            "skill-a": {
                "capsule_path": ".dormant/mimiraether/skill-a",
                "original_category": "mimiraether",
                "dormant_at": "2026-07-12T04:37:29.543491+00:00",
                "summary": "S" * 165,
            }
        },
        "skill_usage": {"skill-a": 3},
        "curator_nudge": "nudge-text",
    }


def _slim_disk() -> dict:
    """已瘦身的磁盘态（作为 merge 的 disk 侧）。"""
    d = _dirty_state()
    normalize(d)
    return d


def _merge_fn(disk: dict, mem: dict) -> dict:
    """复刻 ``CrossSessionMemory.merge_disk_into_memory`` 的关键语义：内存胜出。"""
    out = json.loads(json.dumps(mem))
    for key in ("skill_usage", "dormant_skills"):
        if key in disk:
            out[key] = {**(disk.get(key) or {}), **(out.get(key) or {})}
    for key in disk:
        if key not in out:
            out[key] = json.loads(json.dumps(disk[key]))
    disk_prog = disk.get("progress")
    if isinstance(disk_prog, dict):
        mem_prog = out.setdefault("progress", {})
        for key in disk_prog:
            mem_prog.setdefault(key, json.loads(json.dumps(disk_prog[key])))
    return out


# ── A 组：normalize 本体 ─────────────────────────────────────────────────────


def test_a1_drops_and_truncates_all_four_classes():
    data = _dirty_state()
    report = normalize(data)

    assert "milestone_relations" not in data["progress"]
    assert "capsule_path" not in data["dormant_skills"]["skill-a"]
    assert data["dormant_skills"]["skill-a"]["dormant_at"] == "2026-07-12"
    assert len(data["dormant_skills"]["skill-a"]["summary"]) <= MAX_DORMANT_SUMMARY_CHARS
    assert report.changed
    assert len(report.removed) == 2  # milestone_relations + capsule_path
    assert len(report.truncated) == 2  # dormant_at + summary
    assert report.bytes_saved > 0


def test_a2_legal_fields_survive_verbatim():
    data = _dirty_state()
    normalize(data)

    entry = data["dormant_skills"]["skill-a"]
    assert entry["original_category"] == "mimiraether"  # revive_skill:602 在读
    assert data["skill_usage"] == {"skill-a": 3}
    assert data["progress"]["completed_milestones"] == ["m1", "m2"]  # 代码在读
    assert data["progress"]["current_objective"] == "RS20"
    assert data["curator_nudge"] == "nudge-text"
    assert data["memory"]["active_projects"] == []


def test_a3_idempotent_second_run_is_noop():
    data = _dirty_state()
    normalize(data)
    second = normalize(data)

    assert not second.changed
    assert second.bytes_saved == 0


def test_a4_clean_input_reports_unchanged():
    """孪生：本来就是瘦身态 ⇒ 不得谎报 changed（旧重放脚本正是在此撒谎）。"""
    data = _slim_disk()
    report = normalize(data)

    assert not report.changed
    assert report.removed == [] and report.truncated == []


def test_a5_summary_truncation_keeps_tail():
    """头 2/3 + 尾 1/3：结尾的结论不能被砍掉（旧 300 字纯头部截断是 45 处丢失的根因）。"""
    tail_marker = "TAIL-END-MARKER"
    data = _dirty_state()
    data["dormant_skills"]["skill-a"]["summary"] = ("S" * 400) + tail_marker
    normalize(data)

    got = data["dormant_skills"]["skill-a"]["summary"]
    assert len(got) <= MAX_DORMANT_SUMMARY_CHARS
    assert got.endswith(tail_marker)
    assert got.startswith("S")


def test_a6_truncation_never_lengthens():
    """不变短即不改 —— 防「无操作却报改过」。"""
    for payload in ("", "S", "S" * MAX_DORMANT_SUMMARY_CHARS, "S" * (MAX_DORMANT_SUMMARY_CHARS + 1)):
        data = _dirty_state()
        data["dormant_skills"]["skill-a"]["summary"] = payload
        normalize(data)
        assert len(data["dormant_skills"]["skill-a"]["summary"]) <= max(
            len(payload), MAX_DORMANT_SUMMARY_CHARS
        )


def test_a7_malformed_inputs_do_not_raise():
    """非 dict / 段不是 dict / 缺字段 都不得抛（写盘路径不允许因规范化失败而丢数据）。"""
    for payload in ({}, {"progress": None}, {"progress": []}, {"dormant_skills": []}, {"dormant_skills": {"x": 1}}):
        normalize(payload)  # 不抛即通过
    assert normalize(None) is not None  # type: ignore[arg-type]


# ── B 组：真实写入路径（本轮事故的对照臂） ───────────────────────────────────


def test_b1_dirty_memory_cannot_revive_deprecated_fields(tmp_path):
    """本轮缺的那条臂：内存含废弃字段 + 磁盘已瘦身 ⇒ 写盘后仍须为瘦身态。"""
    target = tmp_path / "persistent.json"
    target.write_text(json.dumps(_slim_disk(), ensure_ascii=False), encoding="utf-8")

    ok = persistent_store.save_merged(_dirty_state(), _merge_fn, target)
    assert ok is True

    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert "milestone_relations" not in on_disk["progress"], "旧内存副本复活了废弃字段"
    assert "capsule_path" not in on_disk["dormant_skills"]["skill-a"]
    assert len(on_disk["dormant_skills"]["skill-a"]["dormant_at"]) <= DORMANT_AT_DATE_CHARS
    assert len(on_disk["dormant_skills"]["skill-a"]["summary"]) <= MAX_DORMANT_SUMMARY_CHARS


def test_b2_read_modify_write_path_is_also_guarded(tmp_path):
    """第二条写入路径（skill_curator 走它写 dormant_skills）也须被规范化覆盖。"""
    target = tmp_path / "persistent.json"
    target.write_text(json.dumps(_slim_disk(), ensure_ascii=False), encoding="utf-8")

    def mutator(data: dict) -> None:
        data["progress"]["milestone_relations"] = {"x": {"to": "y"}}
        data["dormant_skills"]["skill-b"] = {"capsule_path": ".dormant/x/skill-b", "summary": "S" * 200}

    persistent_store.read_modify_write(mutator, path=target)

    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert "milestone_relations" not in on_disk["progress"]
    assert "capsule_path" not in on_disk["dormant_skills"]["skill-b"]
    assert len(on_disk["dormant_skills"]["skill-b"]["summary"]) <= MAX_DORMANT_SUMMARY_CHARS


def test_b3_clean_write_stays_clean(tmp_path):
    """孪生：正常写入不得被规范化破坏（value-preserving）。"""
    target = tmp_path / "persistent.json"
    target.write_text(json.dumps(_slim_disk(), ensure_ascii=False), encoding="utf-8")

    persistent_store.save_merged(_slim_disk(), _merge_fn, target)

    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk["dormant_skills"]["skill-a"]["original_category"] == "mimiraether"
    assert on_disk["progress"]["completed_milestones"] == ["m1", "m2"]
    assert on_disk["skill_usage"] == {"skill-a": 3}


# ── C 组：接线守卫 + 哨兵一致性 ─────────────────────────────────────────────


def test_c1_save_path_actually_invokes_normalization():
    """接线守卫：防「模块存在但没人调」（T4 那次的 BR-1 同型病）。"""
    src = (REPO / "agent" / "persistent_store.py").read_text(encoding="utf-8")
    save_fn = src.split("def _save_unlocked", 1)[1]
    assert "normalize_and_log" in save_fn, "_save_unlocked 没有调用规范化 —— 治本未接线"


def test_c1b_all_known_writers_are_covered():
    """**审计面先行**：persistent.json 有两条写入路径，两条都必须接线。

    取证（grep 全仓 open(...,"w")/json.dump 写 persistent 的落点）：
      - agent/persistent_store.py :: _save_unlocked（save / save_merged / read_modify_write 汇此）
      - agent/dream_memory.py     :: _save_persistent（蒸馏专用，**绕过** facade）

    我第一版只接了前者，并称其为「唯一咽喉」—— 那是只扫一层的结论，已更正。
    本用例把「两条都接」变成可断言事实，防止将来新增第三条时无人发现。
    """
    for rel, fn_name in (
        ("agent/persistent_store.py", "_save_unlocked"),
        ("agent/dream_memory.py", "_save_persistent"),
    ):
        src = (REPO / rel).read_text(encoding="utf-8")
        body = src.split(f"def {fn_name}", 1)
        assert len(body) == 2, f"{rel} 找不到 {fn_name}"
        assert "normalize_and_log" in body[1], f"{rel}::{fn_name} 未接线（绕过写盘规范化）"



def test_c2_sentinel_script_agrees_with_normalize(tmp_path):
    """哨兵脚本（机械检查用）与 normalize 必须同源：normalize 后的对象必须无违规。"""
    scripts = REPO / "scripts" / "check_persistent_invariants.py"
    assert scripts.exists(), "哨兵脚本缺失"
    sys.path.insert(0, str(scripts.parent))
    import importlib.util

    spec = importlib.util.spec_from_file_location("_cpi", scripts)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    dirty = _dirty_state()
    assert mod.find_violations(dirty), "哨兵对坏样本失明"
    normalize(dirty)
    assert mod.find_violations(dirty) == [], "哨兵与 normalize 判定不一致"


def test_c3_every_declared_field_has_evidence():
    """声明纪律：每条废弃字段必须给读侧取证与归档落点（防「看起来没用」就删）。"""
    for spec in DEPRECATED_FIELDS:
        assert spec.evidence.strip(), f"{spec.key} 缺读侧取证"
        assert spec.reason.strip(), f"{spec.key} 缺理由"
        if spec.action == "drop":
            assert spec.archived.strip(), f"{spec.key} 是删除类，必须给归档落点"
        else:
            assert spec.limit > 0, f"{spec.key} 是收缩类，必须给上限"


def test_c4_report_shape_is_stable():
    """报告形状稳定（日志/台账消费方依赖它）。"""
    rep = normalize_and_log(_dirty_state(), source="pytest")
    d = rep.as_dict()
    assert set(d) == {"removed", "truncated", "bytes_saved"}
    assert d["removed"] == 2 and d["truncated"] == 2 and d["bytes_saved"] > 0
