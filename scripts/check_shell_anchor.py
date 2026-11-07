#!/usr/bin/env python3
"""部署侧脚本锚 · 让「在跑版改了」在 git diff 里看得见。

为什么需要（2026-11-07 实测）：
  ~/.mimiraether/scripts/* 不进版本控制（home 仓 .gitignore = *）。
  cron 壳 `wiki_quality_gate_monitor.sh` 是门禁的搬运层——
  被改动、或被人改回去，git diff 里什么都看不到。
  2026-11-07 当天三处修（判据 / 播报 / 计数）里，这一层是唯一「改完看不出改过」的。

做法（不新建机制，复用 verify_* 的两向判据形态）：
  锚清单 = 仓库内 scripts/anchors/deployed_scripts.json（进版本控制 ⇒ 改锚有 diff）。
  本脚本把「在跑文件」的 sha256 与锚比对；不符 ⇒ rc=1，并逐条打印期望/实际前缀。

rc 语义（与 wiki 门禁同族：仪表故障 != 发现问题）：
  0 = 全部匹配（含锚为空表——空表不算故障，避免恒红）
  1 = 有漂移（哈希不符 / 在跑文件缺失）
  2 = 锚清单本身不可用（缺失 / JSON 坏 / schema 坏）—— 仪表故障，不是漂移

刻意不做「不匹配就自动更新锚」：那等于没有闸。
  --update 必须显式调用，且结果要提交 diff 才生效。

自限（诚实边界）：本闸检出**误改 / 回退**，不检出**恶意删除**——
  把壳里的调用行删掉，本闸就看不见（自指）。它买的是「改动可见」，不是「防篡改」。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "scripts" / "anchors" / "deployed_scripts.json"


def sha256_file(path: Path) -> str | None:
    """文件 sha256 hex；不可读 ⇒ None（不抛，交给调用方判 missing）。"""
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def expand(path: str) -> str:
    """把 `~/...` 展开（锚清单只存 `~`，不存 home 绝对路径——防个人信息随仓库外泄）。"""
    return os.path.expanduser(path)


def validate_entries(entries) -> list[str]:
    """纯：schema 校验。返回问题清单（空 = 通过）。"""
    problems: list[str] = []
    if not isinstance(entries, list):
        return ["anchors 必须是数组"]
    seen: set[str] = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"anchors[{i}] 不是对象")
            continue
        p = e.get("path")
        s = e.get("sha256")
        if not isinstance(p, str) or not p.strip():
            problems.append(f"anchors[{i}].path 缺失或非字符串")
            continue
        if not isinstance(s, str) or len(s.strip()) != 64:
            problems.append(f"anchors[{i}].sha256 必须是 64 位 hex（{p}）")
        if p in seen:
            problems.append(f"anchors 重复路径 {p}")
        seen.add(p)
    return problems


def evaluate(entries: list[dict], actual: dict[str, str | None]) -> tuple[int, list[str]]:
    """纯：entries=锚条目；actual={path: 实测哈希或 None}。返回 (rc, 输出行)。

    纯函数（不碰盘）⇒ 正控/负控可各喂一组输入，不必造真文件。
    """
    drift: list[str] = []
    missing = 0
    for e in entries:
        p = e.get("path", "?")
        want = (e.get("sha256") or "").strip().lower()
        got = actual.get(p)
        if got is None:
            missing += 1
            drift.append(f"DRIFT missing  {p}  want={want[:12]}")
        elif got != want:
            drift.append(f"DRIFT changed  {p}  want={want[:12]} got={got[:12]}")
    head = f"anchors={len(entries)} drift={len(drift)} missing={missing}"
    return (1 if drift else 0), [head] + drift


def load_manifest(path: Path) -> tuple[list[dict] | None, str | None]:
    """读锚清单。返回 (entries, err)；err 非空 ⇒ rc=2。"""
    if not path.exists():
        return None, f"锚清单缺失 {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"锚清单不可解析 {path}: {exc}"
    if not isinstance(data, dict):
        return None, "锚清单顶层必须是对象"
    entries = data.get("anchors")
    problems = validate_entries(entries)
    if problems:
        return None, "schema 坏: " + "; ".join(problems)
    return entries, None


def collect_actual(entries: list[dict]) -> dict[str, str | None]:
    return {e["path"]: sha256_file(Path(expand(e["path"]))) for e in entries}


def _selftest() -> int:
    """两向自证：正控（该报的报）与负控（不该报的不报）各须给对。

    防「双绿 = 检测器已死」：任一例不符即 rc=1。
    """
    h1 = "a" * 64
    h2 = "b" * 64
    cases: list[tuple[str, list[dict], dict[str, str | None], int, str]] = [
        # name, entries, actual, want_rc, 必须出现的子串
        ("pos_match", [{"path": "~/.x", "sha256": h1}], {"~/.x": h1}, 0, "drift=0"),
        ("pos_changed", [{"path": "~/.x", "sha256": h1}], {"~/.x": h2}, 1, "DRIFT changed"),
        ("pos_missing", [{"path": "~/.x", "sha256": h1}], {"~/.x": None}, 1, "DRIFT missing"),
        ("boundary_empty", [], {}, 0, "anchors=0"),
        ("neg_extra_actual", [{"path": "~/.x", "sha256": h1}],
         {"~/.x": h1, "~/.y": h2}, 0, "anchors=1"),
        ("case_insensitive", [{"path": "~/.x", "sha256": h1.upper()}],
         {"~/.x": h1}, 0, "drift=0"),
    ]
    bad = 0
    for name, entries, actual, want_rc, needle in cases:
        rc, lines = evaluate(entries, actual)
        out = "\n".join(lines)
        ok = rc == want_rc and needle in out
        bad += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name} rc={rc} want_rc={want_rc}")

    # schema 校验两向：好 schema 过、坏 schema 拦
    good = [{"path": "~/.x", "sha256": h1}]
    for name, entries, want_empty in (
        ("schema_good", good, True),
        ("schema_bad_len", [{"path": "~/.x", "sha256": "abc"}], False),
        ("schema_bad_missing_path", [{"sha256": h1}], False),
        ("schema_dup", good + good, False),
        ("schema_not_list", {"path": 1}, False),
    ):
        probs = validate_entries(entries)
        ok = (not probs) if want_empty else bool(probs)
        bad += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name} problems={len(probs)}")

    # 端到端（真文件，临时目录）：改一个字节必须翻红，还原必须转绿
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "s.sh"
        f.write_text("echo hi\n", encoding="utf-8")
        ent = [{"path": str(f), "sha256": sha256_file(f) or ""}]
        rc_ok, _ = evaluate(ent, collect_actual(ent))
        f.write_text("echo hi\n# tampered\n", encoding="utf-8")
        rc_bad, _ = evaluate(ent, collect_actual(ent))
        f.write_text("echo hi\n", encoding="utf-8")
        rc_back, _ = evaluate(ent, collect_actual(ent))
        ok = (rc_ok, rc_bad, rc_back) == (0, 1, 0)
        bad += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] e2e_tamper rc={rc_ok}->{rc_bad}->{rc_back}")

    print(f"selftest={'PASS' if bad == 0 else 'FAIL'} failed={bad}")
    return 0 if bad == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="部署侧脚本锚（sha256 漂移）")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--update", action="store_true", help="把实测哈希写回锚清单（须提交 diff）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return _selftest()

    mpath = Path(a.manifest)
    entries, err = load_manifest(mpath)
    if err:
        print(f"[anchor] ⚠ 锚清单不可用: {err}")
        return 2

    actual = collect_actual(entries)

    if a.update:
        changed = 0
        for e in entries:
            got = actual.get(e["path"])
            if got is None:
                print(f"[anchor] ⚠ 跳过（在跑文件缺失，锚保留旧值）: {e['path']}")
                continue
            if got != e["sha256"].strip().lower():
                print(f"[anchor] 更新 {e['path']}  {e['sha256'][:12]} -> {got[:12]}")
                e["sha256"] = got
                changed += 1
        if changed:
            data = json.loads(mpath.read_text(encoding="utf-8"))
            data["anchors"] = entries
            mpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[anchor] updated={changed}（须 git add 锚清单并提交，否则改动仍不可见）")
        return 0

    rc, lines = evaluate(entries, actual)
    for line in lines:
        print(line)
    if rc != 0:
        print("[anchor] ⚠ 在跑脚本与锚不符——若是有意改动，跑 --update 并提交锚 diff")
    return rc


if __name__ == "__main__":
    sys.exit(main())
