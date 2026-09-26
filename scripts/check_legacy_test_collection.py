#!/usr/bin/env python3
"""U10b: tests/legacy zero-collection drift sentinel (2026-09-26).

背景
--------------------------------------------------------------------------------
``tests/legacy`` 自带 ``conftest.py`` 的 ``collect_ignore_glob = ["*.py"]`` ⇒ 整目录
**静默不收集**：目录里有 .py 测试文件，``pytest`` 实际收集到 0 条。
该停放态是**有意设计**（2026-09-18 批2.3「游离测试停放区」），但结构与 U10
「注释覆盖」同形 —— **看着有测试，实际没有一条在跑**。

本检查**不做常驻报红**（恒红会训练人忽略门禁），只在**清单漂移**时报 FAIL：

    .py 文件数 > 0  AND  收集数 == 0  AND  文件清单 != 基线

⇒ 有人往停放区放了东西，却没意识到它不会跑。基线用 ``--update-baseline``
显式刷新（等于登记一次「我知道它不跑」）。

用法
--------------------------------------------------------------------------------
    python3 scripts/check_legacy_test_collection.py                # 查真实对象
    python3 scripts/check_legacy_test_collection.py --selftest     # 受控双测
    python3 scripts/check_legacy_test_collection.py --update-baseline

退出码：0 = PASS，1 = FAIL，2 = 用法/环境错误。
输出末行恒为 ``VERDICT: PASS`` / ``VERDICT: FAIL``（供 mech_checks verdict_parse）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PARK_REL = "tests/legacy"


def _mimir_home() -> Path:
    """Runtime data root: env-first, immune to the ``$HOME`` double-nesting."""
    for key in ("MIMIR_HOME", "MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        v = os.environ.get(key, "").strip()
        if v:
            return Path(v).expanduser()
    home = Path.home()
    return home if home.name == ".mimiraether" else home / ".mimiraether"


DEFAULT_BASELINE = _mimir_home() / "data" / "ops" / "legacy_tests_baseline.json"


def inventory(park_dir: Path) -> dict:
    """Top-level ``*.py`` -> sha256. ``__pycache__`` 不算内容。"""
    out = {}
    if not park_dir.is_dir():
        return out
    for f in sorted(park_dir.glob("*.py")):
        if f.is_file():
            out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def collect_count(repo: Path, park_rel: str, timeout_s: int = 300):
    """真实 pytest 收集数。返回 int，**跑不动返回 None**（不得读成 0）。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", park_rel, "--collect-only", "-q"],
            cwd=str(repo), capture_output=True, text=True, timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return sum(1 for line in text.splitlines() if "::" in line)


def assess(inv: dict, collected, baseline) -> tuple:
    """纯函数判据：返回 (verdict, hints)。"""
    if not inv:
        return "PASS", ["停放区无 .py 文件"]
    if collected is None:
        return "ERROR", ["pytest 收集失败：无法判定（不得读成 0）"]
    if collected > 0:
        return "PASS", [f"collected={collected}（文件会跑，停放态已结束）"]
    if not baseline or not isinstance(baseline.get("files"), dict):
        return "PASS", ["基线未建立 ⇒ 本次记录；此后清单漂移即 FAIL"]
    old = baseline["files"]
    if old == inv:
        return "PASS", [f"{len(inv)} 个 .py 停在停放区、collected=0（既定态，已登记）"]
    added = sorted(set(inv) - set(old))
    removed = sorted(set(old) - set(inv))
    changed = sorted(k for k in set(inv) & set(old) if inv[k] != old[k])
    hints = ["清单漂移（有人往停放区放了东西，但它不会跑）："]
    if added:
        hints.append("  新增: " + ", ".join(added))
    if changed:
        hints.append("  改动: " + ", ".join(changed))
    if removed:
        hints.append("  删除: " + ", ".join(removed))
    hints.append("  处置：让它们真跑（移出停放区）或登记基线 --update-baseline")
    return "FAIL", hints


def _selftest() -> int:
    """受控双测：坏样本必拦 / 孪生不误拦。"""
    import tempfile
    arms = []
    with tempfile.TemporaryDirectory() as td:
        park = Path(td)
        (park / "a_test.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
        inv = inventory(park)
        base = {"files": dict(inv)}
        arms.append(("A 清单==基线", assess(inv, 0, base)[0], "PASS"))
        arms.append(("B 收集>0（孪生）", assess(inv, 3, base)[0], "PASS"))
        arms.append(("C 空停放区（孪生）", assess({}, 0, base)[0], "PASS"))
        arms.append(("D 无基线", assess(inv, 0, None)[0], "PASS"))
        arms.append(("E 收集失败", assess(inv, None, base)[0], "ERROR"))
        (park / "new_test.py").write_text("def test_b():\n    assert True\n", encoding="utf-8")
        arms.append(("F 新增文件（坏样本）", assess(inventory(park), 0, base)[0], "FAIL"))
        (park / "a_test.py").write_text("# changed\n", encoding="utf-8")
        arms.append(("G 内容改动（坏样本）", assess(inventory(park), 0, base)[0], "FAIL"))
        (park / "new_test.py").unlink()
        arms.append(("H 文件删除（坏样本）", assess(inventory(park), 0, base)[0], "FAIL"))
    bad = [f"{n}: got {g} want {w}" for n, g, w in arms if g != w]
    for n, g, w in arms:
        print(f"  [{'ok' if g == w else 'BAD'}] {n}: {g}")
    if bad:
        print("SELFTEST: FAIL")
        for b in bad:
            print("  " + b)
        return 1
    print(f"SELFTEST: PASS ({len(arms)} arms)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--park", default="", help=f"停放区相对路径（默认 {PARK_REL}）")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--update-baseline", action="store_true", help="登记当前清单为基线")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    repo = Path(args.repo).expanduser()
    park_rel = args.park or PARK_REL
    park_dir = repo / park_rel
    inv = inventory(park_dir)
    collected = collect_count(repo, park_rel)
    bpath = Path(args.baseline).expanduser()
    baseline = None
    if bpath.exists():
        try:
            baseline = json.loads(bpath.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"基线不可读: {type(exc).__name__}: {exc}")

    verdict, hints = assess(inv, collected, baseline)
    print(f"park dir  : {park_dir}")
    print(f"inventory : {len(inv)} file(s)")
    print(f"collected : {'N/A(跑不动)' if collected is None else collected}")
    print(f"baseline  : {bpath}")
    for h in hints:
        print("HINT: " + h)

    if args.update_baseline and verdict == "PASS":
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(json.dumps(
            {"files": inv, "park_rel": park_rel, "recorded_by": "check_legacy_test_collection"},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"HINT: 基线已写入 {bpath}（{len(inv)} file(s)）")
    print(f"VERDICT: {verdict}")
    return 0 if verdict == "PASS" else (1 if verdict == "FAIL" else 2)


if __name__ == "__main__":
    sys.exit(main())
