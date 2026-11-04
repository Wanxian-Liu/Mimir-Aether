#!/usr/bin/env python3
"""自我矛盾报告去重量具（两向控制 + 一次性迁移）。

用法:
  --selftest   临时 HOME 造正控/负控/窗口/复现前缀/历史注入，验语义本身（不碰真库）
  --check      对真库跑一致性检查（只读，不写盘）
  --migrate    一次性：把存量逐字重复条目合并（写前备份，幂等）

判据（§8.5 形态 1 脚本）:
  重跑命令: ~/src/MimirAether/.venv/bin/python3 ~/src/MimirAether/scripts/contradiction_dedup_probe.py --selftest
  复算数字: rc=0 且 POS entries=1 repeat=2 / NEG entries=2 / WIN entries=10 / REP entries=1 repeat=3 / HIST 两向
            / RES 四项（POS 过滤生效 / NEG 未标仍在 / VAR 8 变体 / REPEAT 复发只累加不复活）
"""
import argparse
import datetime as _dt
import json
import os
import pathlib
import shutil
import sys
import tempfile

# 仓根由文件位置推导（公开仓禁绝对 home 路径）
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
sys.path.insert(0, _REPO_ROOT)


def _load():
    from agent import dream_memory  # noqa: E402

    return dream_memory


def _read(path):
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def selftest() -> int:
    dm = _load()
    tmp = tempfile.mkdtemp(prefix="probe-contra-")
    os.environ["MIMIR_AETHER_HOME"] = tmp
    path = dm._get_contradiction_path()
    results = {}
    try:
        dm._save_contradiction_report("决策「甲」与模式「乙」冲突：样本A")
        dm._save_contradiction_report("决策「甲」与模式「乙」冲突：样本A")
        d = _read(path)
        results["POS"] = len(d) == 1 and int(d[0].get("repeat_count") or 0) == 2
        print(f"POS entries={len(d)} repeat={d[0].get('repeat_count') if d else None} -> {'seen' if results['POS'] else 'none'}")
        print(f"POS brief: {dm._contradiction_brief(d[0]['contradiction'])[:44] if d else ''}")

        # 复现前缀：模型按指令加 `[复现]` ⇒ 应并入同一条（否则永远匹配不上）
        dm._save_contradiction_report("[复现] 决策「甲」与模式「乙」冲突：样本A")
        d = _read(path)
        results["REP"] = len(d) == 1 and int(d[0].get("repeat_count") or 0) == 3
        print(f"REP entries={len(d)} repeat={d[0].get('repeat_count') if d else None} -> {'seen' if results['REP'] else 'none'}")

        dm._save_contradiction_report("决策「丙」与模式「丁」冲突：样本B")
        d = _read(path)
        results["NEG"] = len(d) == 2 and int(d[1].get("repeat_count") or 0) == 1
        print(f"NEG entries={len(d)} repeat={d[1].get('repeat_count') if len(d) > 1 else None} -> {'seen' if results['NEG'] else 'none'}")

        for i in range(11):
            dm._save_contradiction_report(f"窗口样本 {i:02d} 号矛盾")
        d = _read(path)
        texts = [x.get("contradiction") for x in d]
        results["WIN"] = len(d) == 10 and "窗口样本 00 号矛盾" not in texts
        print(f"WIN entries={len(d)} oldest_dropped={'窗口样本 00 号矛盾' not in texts} -> {'seen' if results['WIN'] else 'none'}")

        # 历史注入：有历史 ⇒ prompt 必须带 [已报 1]；无历史 ⇒ 必须不带
        hist = dm._recent_contradictions()
        p_hist = dm._build_distillation_prompt("样本记忆", hist)
        p_empty = dm._build_distillation_prompt("样本记忆", [])
        results["HIST"] = ("[已报 1]" in p_hist) and ("[已报 1]" not in p_empty)
        print(f"HIST with_history={'[已报 1]' in p_hist} without={('[已报 1]' in p_empty)} limit={len(hist)} -> {'seen' if results['HIST'] else 'none'}")
        results["PROMPT_RENDER"] = ("{contradiction_history}" not in p_hist) and ("最严重的自我矛盾" in p_hist)
        print(f"PROMPT_RENDER clean={'{contradiction_history}' not in p_hist} -> {'seen' if results['PROMPT_RENDER'] else 'none'}")
        # resolved 白名单（11-03 卡 §4-2）：过滤生效两向 + 值域变体 + 复发不静默
        d = _read(path)
        before = dm._recent_contradictions(limit=50)
        target = d[0]
        target["resolved"] = "2026-11-04 正控：人工裁定示例"
        _write(path, d)
        after = dm._recent_contradictions(limit=50)
        results["RES_POS"] = len(after) == len(before) - 1 and target["contradiction"] not in after
        print(f"RES_POS before={len(before)} after={len(after)} -> {'seen' if results['RES_POS'] else 'none'}")
        results["RES_NEG"] = d[1]["contradiction"] in after
        print(f"RES_NEG unresolved_kept={d[1]['contradiction'] in after} -> {'seen' if results['RES_NEG'] else 'none'}")
        results["RES_VAR"] = (
            dm._is_resolved({"resolved": True})
            and dm._is_resolved({"resolved": "2026-11-04 A族已转台账T-A1"})
            and dm._is_resolved({"resolved": "  2026-11-04 前导空格仍算已解决"})
            and not dm._is_resolved({})
            and not dm._is_resolved({"resolved": None})
            and not dm._is_resolved({"resolved": ""})
            and not dm._is_resolved({"resolved": "pending"})
            and not dm._is_resolved({"resolved": "todo"})
            and not dm._is_resolved({"resolved": "待定"})
            and not dm._is_resolved({"resolved": "未解决"})
            and not dm._is_resolved({"resolved": "n/a"})
            and not dm._is_resolved({"resolved": " false "})
            and not dm._is_resolved({"resolved": "0"})
            and not dm._is_resolved({"resolved": "TRUE"})
            and not dm._is_resolved({"resolved": "Yes"})
        )
        print(f"RES_VAR pos=3 neg=12 -> {'seen' if results['RES_VAR'] else 'none'}")
        rep_before = int(target.get("repeat_count") or 1)
        dm._save_contradiction_report(target["contradiction"])
        d2 = _read(path)
        results["RES_REPEAT"] = (
            len(d2) == len(d)
            and int(d2[0].get("repeat_count") or 0) == rep_before + 1
            and dm._is_resolved(d2[0])
        )
        print(f"RES_REPEAT entries={len(d2)} repeat={d2[0].get('repeat_count')} still_resolved={dm._is_resolved(d2[0])} -> {'seen' if results['RES_REPEAT'] else 'none'}")

    finally:
        os.environ.pop("MIMIR_AETHER_HOME", None)
        shutil.rmtree(tmp, ignore_errors=True)

    ok = all(results.values())
    print("checks: " + " ".join(f"{k}={'P' if v else 'F'}" for k, v in results.items()))
    print(f"RESULT: {'PASS' if ok else 'FAIL'} rc={0 if ok else 1}")
    return 0 if ok else 1


def check() -> int:
    dm = _load()
    path = dm._get_contradiction_path()
    d = _read(path)
    print(f"file: {path}")
    print(f"entries: {len(d)} (cap 10)")
    if not d:
        print("EMPTY -> rc=1")
        return 1
    uniq = len({(x.get("contradiction") or "").strip() for x in d if isinstance(x, dict)})
    reps = [int(x.get("repeat_count") or 1) for x in d if isinstance(x, dict)]
    missing = [i for i, x in enumerate(d) if isinstance(x, dict) and "repeat_count" not in x]
    for i, x in enumerate(d, 1):
        ts = (x.get("first_seen") or x.get("timestamp") or "")[:19]
        res = "Y" if dm._is_resolved(x) else "-"
        print(f"  {i:2d}. {ts}  rep={x.get('repeat_count', '-')}  res={res}  {(x.get('contradiction') or '')[:52]}")
    print(f"idents: {uniq} / dup_entries: {len(d) - uniq} / max_repeat: {max(reps) if reps else 0}")
    resolved_n = sum(1 for x in d if dm._is_resolved(x))
    visible = len(dm._recent_contradictions(limit=50))
    print(f"resolved: {resolved_n} / prompt_visible: {visible} (filtered={len(d) - visible})")
    print(f"legacy_entries_missing_repeat_count: {len(missing)}")
    ok = uniq == len(d)
    print(f"RESULT: {'PASS' if ok else 'FAIL'} rc={0 if ok else 1}")
    return 0 if ok else 1


def migrate() -> int:
    dm = _load()
    path = dm._get_contradiction_path()
    d = _read(path)
    if not d:
        print("EMPTY -> nothing to migrate, rc=0")
        return 0

    merged: dict = {}
    for x in d:
        if not isinstance(x, dict):
            continue
        text = (x.get("contradiction") or "").strip()
        if not text:
            continue
        ts = x.get("timestamp") or ""
        if text in merged:
            cur = merged[text]
            cur["repeat_count"] = int(cur.get("repeat_count") or 1) + int(x.get("repeat_count") or 1)
            if ts and ts > (cur.get("last_seen") or ""):
                cur["last_seen"] = ts
        else:
            merged[text] = {
                "timestamp": ts,
                "first_seen": x.get("first_seen") or ts,
                "last_seen": x.get("last_seen") or ts,
                "repeat_count": int(x.get("repeat_count") or 1),
                "contradiction": text,
            }
    out = list(merged.values())
    changed = len(out) != len(d)

    print(f"before: {len(d)} -> after: {len(out)} (changed={changed})")
    if not changed:
        print("already deduped -> rc=0")
        return 0

    bak_dir = os.path.join(
        os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether"),
        "data",
        "backups",
    )
    os.makedirs(bak_dir, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = os.path.join(bak_dir, f"self_contradiction_report.{stamp}.json")
    shutil.copy2(path, bak)
    print(f"backup: {bak} ({os.path.getsize(bak)} B)")

    _write(path, out)
    back = _read(path)
    ok = len(back) == len(out) and len({(x.get("contradiction") or "").strip() for x in back}) == len(back)
    for i, x in enumerate(back, 1):
        print(f"  {i:2d}. rep={x.get('repeat_count')}  {(x.get('contradiction') or '')[:52]}")
    print(f"RESULT: {'PASS' if ok else 'FAIL'} rc={0 if ok else 1}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--migrate", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.check:
        sys.exit(check())
    if a.migrate:
        sys.exit(migrate())
    ap.print_help()
    sys.exit(2)
