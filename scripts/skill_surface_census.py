#!/usr/bin/env python3
"""技能解析面普查 —— 四条腿到底各看见多少、是不是同一个东西。

背景（2026-11-02 四方专项卡）：
  「一个技能」在盘上可能对应 1~3 份 SKILL.md，而代码里有四条独立的解析路径。
  本脚本把「同一技能名，各腿落在哪」量出来，供复核方原样复算。

用法:
  ~/src/MimirAether/.venv/bin/python3 scripts/skill_surface_census.py
  ~/src/MimirAether/.venv/bin/python3 scripts/skill_surface_census.py --json

输出判据（默认文本模式）:
  L1 skills_list                = <n>     枚举腿
  L2 skill_view(_get_skill_dir) = <n>     读取腿
  L3 skill_manage(_find_skill)  = <n>     管理腿（影子实现）
  真值（两树全部 SKILL.md 名）= <n>  |  SKILL.md 文件数 = <n>
  同名重复 = <k> 个名字 / <m> 份文件
  读腿与写腿落点不同 = <x> / <y>

退出码：0 = 正常产出；1 = 某条腿导入失败（读数不完整，不得引用）
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _roots():
    """两棵技能树：仓库侧 + 数据根侧。"""
    out = [REPO / "skills"]
    try:
        from mimiraether_constants import get_mimiraether_home
        out.append(get_mimiraether_home() / "skills")
    except Exception:
        out.append(Path.home() / ".mimiraether" / "skills")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--sample", type=int, default=12, help="读/写落点抽样个数")
    a = ap.parse_args()

    data = {}
    try:
        import skills.skills_loader as SL
        import tools.skill_manager_tool as SMT
        from agent.skill_utils import get_all_skills_dirs
    except Exception as e:  # 导入失败 = 读数不完整
        print(f"IMPORT-FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    ROOTS = _roots()
    all_md = []
    for r in ROOTS:
        if r.exists():
            all_md.extend(r.rglob("SKILL.md"))
    by_name = {}
    for p in all_md:
        by_name.setdefault(p.parent.name, []).append(p)
    ALL = set(by_name)
    dups = {k: sorted(v) for k, v in by_name.items() if len(v) > 1}

    L1 = {s.get("name") for s in SL.skills_list()}
    L2 = {n for n in ALL if SL._get_skill_dir(n) is not None}
    L3 = {n for n in ALL if SMT._find_skill(n) is not None}
    data["L1_skills_list"] = len(L1)
    data["L2_skill_view"] = len(L2)
    data["L3_skill_manage"] = len(L3)
    data["truth_names"] = len(ALL)
    data["skill_md_files"] = len(all_md)
    data["dup_names"] = len(dups)
    data["dup_files"] = sum(len(v) for v in dups.values())
    data["roots"] = [str(p).replace(str(Path.home()), "~") for p in get_all_skills_dirs()]

    sample = sorted(dups)[: a.sample]
    mismatch, rows = 0, []
    for name in sample:
        v = SL._get_skill_dir(name)
        m = SMT._find_skill(name)
        mp = m["path"] if m else None
        same = bool(v and mp and Path(v).resolve() == Path(mp).resolve())
        if not same:
            mismatch += 1
        rows.append({
            "name": name,
            "view": str(v).replace(str(Path.home()), "~") if v else None,
            "manage": str(mp).replace(str(Path.home()), "~") if mp else None,
            "same": same,
        })
    data["sample_n"] = len(sample)
    data["read_write_mismatch"] = mismatch
    data["legs"] = rows

    sym_link_cases = []
    for root in ROOTS:
        if not root.exists():
            continue
        for item in root.iterdir():
            if item.is_symlink() and (item / "SKILL.md").exists():
                sym_link_cases.append({
                    "name": item.name,
                    "in_list": item.name in L1,
                    "in_view": SL._get_skill_dir(item.name) is not None,
                    "in_manage": SMT._find_skill(item.name) is not None,
                })
    data["symlink_skills"] = sym_link_cases

    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"L1 skills_list                = {data['L1_skills_list']}")
    print(f"L2 skill_view(_get_skill_dir) = {data['L2_skill_view']}")
    print(f"L3 skill_manage(_find_skill)  = {data['L3_skill_manage']}")
    print(f"真值（两树全部 SKILL.md 名）= {data['truth_names']}  |  SKILL.md 文件数 = {data['skill_md_files']}")
    print(f"同名重复 = {data['dup_names']} 个名字 / {data['dup_files']} 份文件")
    print(f"get_all_skills_dirs() = {data['roots']}")
    print(f"读腿与写腿落点不同 = {data['read_write_mismatch']} / {data['sample_n']}")
    for r in rows[:6]:
        print(f"  {r['name']:28} view={r['view']}  manage={r['manage']}  same={r['same']}")
    for s in sym_link_cases:
        print(f"  符号链接技能 {s['name']}: list={s['in_list']} view={s['in_view']} manage={s['in_manage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
