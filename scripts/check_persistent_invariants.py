#!/usr/bin/env python3
"""persistent.json 不变量检查（RS20 · 机械检查项 + 治本回归臂）。

背景
--------------------------------------------------------------------------------
2026-09-26：对 ``data/persistent.json`` 的瘦身会被系统自己回滚（旧内存副本整文件重写）。
治本 = 写盘前在 ``agent/persistent_store._save_unlocked`` 消除废弃字段
（``agent/persistent_normalize.py``）。

本脚本是那条治本的**外部独立哨兵**：它不读内存、不读代码逻辑，只读**盘上的
persistent.json**，断言废弃字段不存在。因此即便将来有人在别处新增一条写入路径
绕开 ``persistent_store``，这里也会红 —— 这是「防复发」与「防漏路」的分离。

用法
--------------------------------------------------------------------------------
    python3 scripts/check_persistent_invariants.py              # 查真实对象
    python3 scripts/check_persistent_invariants.py --selftest   # 受控双测（孪生臂）
    python3 scripts/check_persistent_invariants.py --path FILE  # 指定文件

退出码：0 = PASS，1 = FAIL，2 = 用法/环境错误。
输出末行恒为 ``VERDICT: PASS`` 或 ``VERDICT: FAIL``（供 mech_checks verdict_parse）。
"""

from __future__ import annotations

import argparse
import os
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent.persistent_normalize import (  # noqa: E402
    DORMANT_AT_DATE_CHARS,
    MAX_DORMANT_SUMMARY_CHARS,
    normalize,
)

def _mimir_home() -> Path:
    """Runtime data root: env-first, and immune to the ``$HOME`` double-nesting.

    ``$HOME`` is already the runtime root inside agent sandboxes; appending
    ``.mimiraether`` again yields ``<root>/.mimiraether`` and the default path
    silently misses (2026-09-26: two mech-checks items reported "unparseable"
    for exactly this reason).
    """
    for key in ("MIMIR_HOME", "MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        v = os.environ.get(key, "").strip()
        if v:
            return Path(v).expanduser()
    home = Path.home()
    return home if home.name == ".mimiraether" else home / ".mimiraether"

DEFAULT_PATH = _mimir_home() / "data" / "persistent.json"


def find_violations(data: dict) -> list[str]:
    """返回违规明细（空 = 无违规）。只读断言，不改数据。"""
    bad: list[str] = []
    if not isinstance(data, dict):
        return ["<root> 不是 dict"]

    prog = data.get("progress")
    if isinstance(prog, dict) and "milestone_relations" in prog:
        bad.append(f"progress.milestone_relations 仍存在（{len(prog['milestone_relations'])} 键）")

    skills = data.get("dormant_skills")
    if isinstance(skills, dict):
        n_cap = n_at = n_sum = 0
        for entry in skills.values():
            if not isinstance(entry, dict):
                continue
            if "capsule_path" in entry:
                n_cap += 1
            at = entry.get("dormant_at")
            if isinstance(at, str) and len(at) > DORMANT_AT_DATE_CHARS:
                n_at += 1
            sm = entry.get("summary")
            if isinstance(sm, str) and len(sm) > MAX_DORMANT_SUMMARY_CHARS:
                n_sum += 1
        if n_cap:
            bad.append(f"dormant_skills[*].capsule_path 仍存在（{n_cap} 条）")
        if n_at:
            bad.append(f"dormant_skills[*].dormant_at 仍为完整时间戳（{n_at} 条）")
        if n_sum:
            bad.append(f"dormant_skills[*].summary 超 {MAX_DORMANT_SUMMARY_CHARS} 字（{n_sum} 条）")
    return bad


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_real(path: Path) -> int:
    if not path.exists():
        print(f"FAIL: 文件不存在 {path}", file=sys.stderr)
        return 2
    data = _load(path)
    bad = find_violations(data)
    print(f"target : {path}  ({path.stat().st_size:,} B)")
    print(f"keys   : {sorted(data.keys())}")
    print(f"skills : {len(data.get('dormant_skills') or {})} 条 dormant")
    if bad:
        for line in bad:
            print(f"  - {line}")
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


def _dirty() -> dict:
    """坏样本：含全部四类废弃字段。"""
    return {
        "version": "1.4",
        "memory": {"key_decisions": [], "learned_patterns": []},
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
    }


def _clean_twin() -> dict:
    """孪生（干净）：同上，但四类废弃字段都不存在；其余字段必须逐值保留。"""
    return {
        "version": "1.4",
        "memory": {"key_decisions": [], "learned_patterns": []},
        "progress": {"current_objective": "RS20", "completed_milestones": ["m1", "m2"]},
        "dormant_skills": {
            "skill-a": {
                "original_category": "mimiraether",
                "dormant_at": "2026-07-12",
                "summary": "S" * MAX_DORMANT_SUMMARY_CHARS,
            }
        },
        "skill_usage": {"skill-a": 3},
    }


def _arms() -> list[tuple[str, bool]]:
    """构造受控双测臂：``(臂名, 期望是否 PASS)``。"""
    arms: list[tuple[str, bool]] = []

    d = _dirty()
    # 注意：本元组第二项 = 「该臂的断言是否成立」。坏样本的正确断言是**探到违规**。
    arms.append(("A1 坏样本·四类废弃字段 ⇒ 必须红", bool(find_violations(d))))
    c = _clean_twin()
    arms.append(("A2 孪生·干净 ⇒ 必须绿", find_violations(c) == []))

    # 分项：逐个只加一类，确认判据有鉴别力（不会一类掩盖另一类）
    for name, mutate, keep in (
        ("milestone_relations", lambda x: x["progress"].__setitem__("milestone_relations", {"a": 1}), None),
        ("capsule_path", lambda x: x["dormant_skills"]["skill-a"].__setitem__("capsule_path", ".dormant/x"), None),
        (
            "dormant_at 全戳",
            lambda x: x["dormant_skills"]["skill-a"].__setitem__("dormant_at", "2026-07-12T04:37:29+00:00"),
            None,
        ),
        ("summary 超长", lambda x: x["dormant_skills"]["skill-a"].__setitem__("summary", "S" * 121), None),
    ):
        dirty2 = _clean_twin()
        mutate(dirty2)
        bad = find_violations(dirty2)
        arms.append((f"A3 单类坏样本「{name}」⇒ 必须红", len(bad) == 1))

    # 边界：恰好达限值必须在绿侧（一分不加不减）
    edge = _clean_twin()
    edge["dormant_skills"]["skill-a"]["summary"] = "S" * MAX_DORMANT_SUMMARY_CHARS
    edge["dormant_skills"]["skill-a"]["dormant_at"] = "2026-07-12"
    arms.append(("A4 边界·恰好达限值 ⇒ 必须绿", find_violations(edge) == []))

    # 治本闭环：normalize 后必须无违规（这是「治本是否覆盖全部四类」的断言）
    n1 = _dirty()
    normalize(n1)
    arms.append(("A5 normalize(坏样本) 后 ⇒ 无违规", find_violations(n1) == []))

    # 幂等：第二次 normalize 报告必须为零改动
    r2 = normalize(n1)
    arms.append(("A6 幂等·二次 normalize ⇒ changed=False", not r2.changed))

    # 非静默：坏样本必须报出改动（防「动了却静默」）
    n2 = _dirty()
    r3 = normalize(n2)
    arms.append(("A7 非静默·坏样本 ⇒ changed=True 且 4 类都报道", r3.changed and len(r3.removed) == 2))

    # 无旁伤：合法字段逐值保留
    arms.append(
        (
            "A8 无旁伤·original_category/skill_usage/milestones 保留",
            n1["dormant_skills"]["skill-a"]["original_category"] == "mimiraether"
            and n1["skill_usage"] == {"skill-a": 3}
            and n1["progress"]["completed_milestones"] == ["m1", "m2"],
        )
    )
    return arms


def run_selftest() -> int:
    ok = True
    for name, passed in _arms():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("VERDICT: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    ap.add_argument("--selftest", action="store_true", help="跑受控双测臂（不查真实对象）")
    args = ap.parse_args(argv)
    if args.selftest:
        return run_selftest()
    return check_real(Path(args.path))


if __name__ == "__main__":
    raise SystemExit(main())
