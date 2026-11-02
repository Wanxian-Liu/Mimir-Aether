"""技能注入面预算量具 —— 量「系统提示里技能索引」的真实成本。

用途：任何「让更多技能进入索引」的改动之前/之后，用它量出每轮固定成本。
出处：wiki/discussions/2026-11-02-技能解析面归一-六条腿一个身份-上游port漂移专项.md §5.4
      （原卡只写「索引会变大」= 形容词；本脚本把它变成读数）

调用（无 shebang，一律显式解释器）：
    ~/src/MimirAether/.venv/bin/python3 scripts/skill_prompt_budget.py
    ... --limit 25000
    ... --project 201 --limit 40000
    ... --selftest

输出（stdout，key=value，机器可读）：
    prompt_bytes / prompt_lines / skills_count / bytes_per_skill / proj_bytes
    limit / verdict = PASS | FAIL | NO-LIMIT

rc 语义：
    0  无限额（仅读数），或 有限额且未超
    1  有限额且超限（G7 判据：注入预算爆了）
    2  导入失败（读数不完整，不得引用）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_prompt():
    """返回 (prompt_text, skills_list)。导入失败抛异常，由 main 转 rc=2。"""
    sys.path.insert(0, str(REPO))
    from skills import skills_loader as sl  # noqa: E402

    return sl.build_skills_prompt(), sl.skills_list()


def _measure(text, skills, project):
    b = len(text.encode("utf-8"))
    n = len(skills) or 1
    per = b / n
    proj = int(round(per * project)) if project else None
    return {
        "prompt_bytes": b,
        "prompt_lines": text.count("\n") + 1,
        "skills_count": len(skills),
        "bytes_per_skill": round(per, 1),
        "proj_bytes": proj,
    }


def _fmt(m):
    out = [
        "prompt_bytes=%d" % m["prompt_bytes"],
        "prompt_lines=%d" % m["prompt_lines"],
        "skills_count=%d" % m["skills_count"],
        "bytes_per_skill=%s" % m["bytes_per_skill"],
    ]
    if m["proj_bytes"] is not None:
        out.append("proj_bytes=%d" % m["proj_bytes"])
    return "\n".join(out)


def _checked_bytes(m):
    """闸要比对的量。

    **坑位（2026-11-02 实证）**：只比 prompt_bytes 会让 `--project` 场景的闸永远 PASS
    —— limit=30000 时现实值 20645 过关，而决策真正关心的是外推值 36723 > 30000。
    正确口径 = max(现值, 外推值)；无外推时就是现值。
    """
    if m["proj_bytes"] is None:
        return m["prompt_bytes"]
    return max(m["prompt_bytes"], m["proj_bytes"])


def _verdict(m, limit):
    """返回 (verdict, rc)。抽成纯函数是为了让闸本身可被 selftest 测到。"""
    if limit is None:
        return "NO-LIMIT", 0
    if _checked_bytes(m) > limit:
        return "FAIL", 1
    return "PASS", 0


def _selftest():
    """量具自检（不读真库）。

    两向（AGENTS §9 档位 4）：
      正控 positive —— 限额充足 => 不超
      负控 negative —— 限额偏低 => 超（闸真会拦）
    控制组样本互不相同，避免同义反复。
    """
    ok = True

    m1 = _measure("x" * 100, ["a", "b", "c", "d"], 8)
    c1 = m1["proj_bytes"] == 200 and not (m1["proj_bytes"] > 1000)

    m2 = _measure("y" * 100, ["a", "b", "c", "d"], 8)
    c2 = m2["proj_bytes"] == 200 and (m2["proj_bytes"] > 150)

    m3 = _measure("z" * 40, ["a", "b"], None)
    c3 = m3["proj_bytes"] is None and m3["bytes_per_skill"] == 20.0

    try:
        m4 = _measure("w" * 10, [], 5)
        c4 = m4["bytes_per_skill"] == 10.0 and m4["proj_bytes"] == 50
    except ZeroDivisionError:
        c4 = False

    # 闸本身的两向（回归 2026-11-02 那个「只比现值 ⇒ 永远 PASS」的 bug）
    m_now = {"prompt_bytes": 20000, "proj_bytes": 36000}
    c5 = _verdict(m_now, 40000) == ("PASS", 0)      # 正控：限额高于外推值 ⇒ 过
    c6 = _verdict(m_now, 30000) == ("FAIL", 1)      # 负控：限额落在外推值与现值之间 ⇒ 拦
    c7 = _verdict(m_now, None) == ("NO-LIMIT", 0)   # 无限额 ⇒ 只报读数
    m_no_proj = {"prompt_bytes": 20000, "proj_bytes": None}
    c8 = _verdict(m_no_proj, 30000) == ("PASS", 0)  # 无外推时不拿幻想值拦人
    c9 = _verdict(m_no_proj, 19000) == ("FAIL", 1)  # 但现值超限仍须拦

    for name, cond in (
        ("positive", c1),
        ("negative", c2),
        ("none-prop", c3),
        ("empty-list", c4),
        ("gate-pass", c5),
        ("gate-fail-projected", c6),
        ("gate-no-limit", c7),
        ("gate-no-proj-pass", c8),
        ("gate-no-proj-fail", c9),
    ):
        print("selftest.%s=%s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and cond
    print("selftest=" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="技能注入面预算量具")
    ap.add_argument("--limit", type=int, default=None, help="prompt_bytes 上限；超出 rc=1")
    ap.add_argument("--project", type=int, default=None, help="按该技能条数线性外推")
    ap.add_argument("--selftest", action="store_true", help="跑量具自检（不读真库）")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    try:
        text, skills = _load_prompt()
    except Exception as exc:
        print("ERROR import_failed: %s: %s" % (type(exc).__name__, exc))
        return 2

    m = _measure(text, skills, a.project)
    print(_fmt(m))
    print("checked_bytes=%d" % _checked_bytes(m))

    if a.limit is not None:
        print("limit=%d" % a.limit)

    verdict, rc = _verdict(m, a.limit)
    print("verdict=%s" % verdict)
    return rc


if __name__ == "__main__":
    sys.exit(main())
