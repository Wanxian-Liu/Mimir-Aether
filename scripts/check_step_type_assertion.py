#!/usr/bin/env python3
"""check_step_type_assertion.py — 「步骤型枚举不给分」那条判据的**可跑断言**。

刘哥 2026-10-26 批示（2026-11-02 复述）：
    「改前把『编号枚举带 首先/然后/最后 ≥2 次 ⇒ 判步骤型不给分』写成可跑断言。」

判据对象（真源）= `agent/parallel_eligibility.py::classify_step_type()`
    is_step_type = (编号/项目符号枚举项 ≥3) AND (步骤词命中 ≥2)
    ⇒ A2 档不给分；checkbox 归 A1，两档不交叉。

用法：
    ~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/scripts/check_step_type_assertion.py --selftest
    ~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/scripts/check_step_type_assertion.py --text-file <任务书>
    （--text 直传会被 terminal 的 CJK 参数闸静默拦 ⇒ 一律走 --text-file）

退出码（两向）：rc=0 全过 / rc=1 有用例失败 / rc=2 环境错（模块导入失败）
⚠️ 边界：本脚本**不**参与触发判定——三档口径尚未生效，只验断言本身。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(os.environ.get("MIMIR_REPO", str(Path.home() / "src/MimirAether")))
sys.path.insert(0, str(REPO))

try:
    from agent.parallel_eligibility import classify_step_type, explain_parallel_elig
except Exception as exc:  # pragma: no cover
    print("IMPORT_FAIL: %s" % exc)
    sys.exit(2)


# ── 用例集（正控 = 不该毙；负控 = 该毙）────────────────────────────────────
NUM10 = "\n".join("%d. 子任务 %d：扫描一处独立目录并汇总读数" % (i, i) for i in range(1, 11))
NUM5 = "\n".join("%d. 第 %d 项独立取证" % (i, i) for i in range(1, 6))
NUM4 = "\n".join("%d) 分支 %d 单独跑一遍" % (i, i) for i in range(1, 5))

CASES = [
    # (id, kind, text, 期望 is_step_type, 期望 hits 含子串)
    ("P1", "正控", NUM10, False, "A2:枚举"),
    ("P2", "正控", NUM5 + "\n首先把口径钉死，再分头跑。", False, "A2:枚举"),
    ("N1", "负控", NUM5 + "\n首先定基线，然后分头跑，最后汇总。", True, "A2:毙"),
    ("N2", "负控", NUM4 + "\n先把环境备好，然后跑，最后回收。", True, "A2:毙"),
    ("N3", "负控", "首先读盘，然后对齐口径，最后落盘。", False, None),
    ("N4", "正控", "- [ ] 扫 A 目录\n- [ ] 扫 B 目录\n- [ ] 扫 C 目录\n然后汇总，最后复核。", False, "A1:checkbox"),
    ("N5", "负控", NUM4 + "\n接着复核，再接着回填。", True, "A2:毙"),
]


def run_case(cid, kind, text, want_step, want_hit):
    st = classify_step_type(text)
    ex = explain_parallel_elig(text)
    fails = []
    if st["is_step_type"] != want_step:
        fails.append("is_step_type=%s want=%s" % (st["is_step_type"], want_step))
    if want_hit and want_hit not in ex["hits"]:
        fails.append("hits 缺 '%s'（实得 %r）" % (want_hit, ex["hits"]))
    if want_step and ex["elig_struct"] >= 2 and "A2:毙" in ex["hits"]:
        pass  # 步骤型不给 A2 —— struct 只可能来自 A1/A3
    return {
        "case": cid, "kind": kind, "step_type": st["is_step_type"],
        "enum_items": st["enum_items"], "step_words": st["step_words"],
        "elig": ex["elig"], "elig_struct": ex["elig_struct"], "elig_kw": ex["elig_kw"],
        "would_trigger": ex["would_trigger"], "hits": ex["hits"],
        "fails": fails,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--text-file", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.text_file:
        txt = Path(a.text_file).read_text(encoding="utf-8", errors="ignore")
        st = classify_step_type(txt)
        ex = explain_parallel_elig(txt)
        print(json.dumps({"step_type": st, "explain": ex}, ensure_ascii=False, indent=2))
        return 0

    if not a.selftest:
        ap.print_help()
        return 0

    results = [run_case(*c) for c in CASES]
    bad = [r for r in results if r["fails"]]
    for r in results:
        tag = "PASS" if not r["fails"] else "FAIL"
        print("[%s] %-3s %-4s step_type=%-5s enum=%d step词=%d struct=%d kw=%d would=%s hits=%s %s" % (
            tag, r["case"], r["kind"], r["step_type"], r["enum_items"], r["step_words"],
            r["elig_struct"], r["elig_kw"], r["would_trigger"], r["hits"],
            ("| " + "; ".join(r["fails"])) if r["fails"] else ""))
    print("SELFTEST cases=%d pass=%d fail=%d rc=%d" % (
        len(results), len(results) - len(bad), len(bad), 0 if not bad else 1))
    if a.json:
        print(json.dumps(results, ensure_ascii=False))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
