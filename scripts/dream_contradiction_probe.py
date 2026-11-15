#!/usr/bin/env python3
"""梦境蒸馏矛盾检测器 · 引文存在性探针（只读）。

用途
----
量化「自我矛盾」报告里被引用的条目是否仍存在于当前记忆。
根因背景：`_build_distillation_prompt()` 把最近未裁定矛盾原文以 `[已报 i]` 喂回
prompt，并指示模型「尽量沿用该条原有措辞」⇒ 旧的引文被冻结并逐日复制，
即便被引的决策早已从记忆中消失。本探针给这条自指环一把可复跑的尺子。

判据语义
--------
* `stale_refs > 0` ⇒ 存在「引用了已不存在条目」的矛盾条目 ⇒ 自指环已发生。
* `stale_refs == 0` 且 `unresolved > 0` ⇒ 历史引文均有效，本探针无告警
  （不代表矛盾为真，只代表引文存活）。

退出码
------
0 = 可读且 stale_refs == 0
1 = 可读且 stale_refs > 0（自指环已发生）
2 = 读文件失败 / 参数错

自测
----
`--selftest` 用内存构造的正/负样本验证判定逻辑，不依赖真实盘上状态；
正控（引文仍在）须 rc=0，负控（引文已删）须 rc=1。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_HOME = os.environ.get("MIMIR_AETHER_HOME") or str(Path.home() / ".mimiraether")

# 引文抽取：中文直角引号 / 双引号 / 弯引号，以及「决策N」「模式N」这类序数引用
_QUOTE_RE = re.compile(r"「([^」]{4,})」")
_TYPO_QUOTE_RE = re.compile(r"[“\"]([^”\"]{4,})[”\"]")

# shingle 覆盖率阈值（字符 4-gram，去空白后）
# 为什么要三态而非纯子串：11-16 实测「交付风格：可逆的我定、不可逆的上收」在现记忆里是
# 「交付风格：给「建议+我负责执行到底」，可逆的我定、不可逆的上收；…」——这是**改写**
# 不是消失。纯子串匹配会把改写误判成 stale（假阳性）。三态口径：
#   present  = 精确子串 → 引文存活
#   partial  = 覆盖率 ∈ [0.20, 0.50) → 改写，视为存活（保守：宁可多喂历史，不误删）
#   absent   = 覆盖率 < 0.20 → 判 stale（引文已不在记忆中）
_THRESH_PRESENT = 0.50
_THRESH_ABSENT = 0.20
_SHINGLE_N = 4


def _shingles(text: str, n: int = _SHINGLE_N) -> set[str]:
    """去空白后取字符 n-gram 集合（中文无词边界，字符 n-gram 已足够）。"""
    t = "".join(str(text).split())
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def ref_status(ref: str, memory_blob: str) -> tuple[str, float]:
    """判定单条引文的存活状态，返回 (status, coverage)。纯函数（便于自测）。

    status ∈ {"present", "partial", "absent"}；只有 "absent" 计入 stale。
    """
    if not ref:
        return "present", 1.0
    if ref in memory_blob:
        return "present", 1.0
    sh = _shingles(ref)
    if not sh:
        return "present", 1.0
    blob_c = "".join(memory_blob.split())
    hit = sum(1 for s in sh if s in blob_c)
    cov = hit / len(sh)
    if cov >= _THRESH_PRESENT:
        return "present", cov
    if cov >= _THRESH_ABSENT:
        return "partial", cov
    return "absent", cov


def _norm(text: object) -> str:
    """对齐口径：压平空白（与 dream_memory._norm_mem_text 同口径）。"""
    if text is None:
        return ""
    return " ".join(str(text).split())


def collect_memory_text(data: dict) -> str:
    """把 persistent.json 的 memory 三段拼成用于检索的大文本。"""
    mem = data.get("memory") or {}
    parts: list[str] = []
    for key in ("key_decisions", "learned_patterns", "behavioral_constraints"):
        for item in mem.get(key) or []:
            if isinstance(item, dict):
                for field in ("decision", "pattern", "rule", "evidence", "context"):
                    val = item.get(field)
                    if isinstance(val, str):
                        parts.append(val)
            elif isinstance(item, str):
                parts.append(item)
    return _norm("\n".join(parts))


def extract_refs(contradiction: str) -> list[str]:
    """从一条矛盾描述里抽取被引用的条目引文。"""
    refs = [m.group(1) for m in _QUOTE_RE.finditer(contradiction or "")]
    if not refs:
        refs = [m.group(1) for m in _TYPO_QUOTE_RE.finditer(contradiction or "")]
    return [_norm(r) for r in refs if _norm(r)]


def classify_entry(entry: dict, memory_blob: str) -> dict:
    """判定单条矛盾的引文存活情况。纯函数（便于自测）。

    只有 status == "absent" 的引文计入 stale（改写 partial 视为存活，保守口径）。
    """
    text = entry.get("contradiction") or ""
    refs = extract_refs(text)
    details = []
    stale = []
    for r in refs:
        status, cov = ref_status(r, memory_blob)
        details.append({"ref": r, "status": status, "coverage": round(cov, 3)})
        if status == "absent":
            stale.append(r)
    return {
        "refs": refs,
        "details": details,
        "stale_refs": stale,
        "is_stale": bool(stale),
    }


def _is_resolved(item: dict) -> bool:
    """与 dream_memory._is_resolved 同语义的正列白名单（只用于统计未裁定数）。"""
    value = item.get("resolved")
    if value is True:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    core = text[:10]
    if len(core) != 10 or core[4] != "-" or core[7] != "-":
        return False
    if not (core[:4] + core[5:7] + core[8:10]).isdigit():
        return False
    import datetime as _dt

    try:
        _dt.datetime.strptime(core, "%Y-%m-%d")
    except ValueError:
        return False
    if len(text) > 10 and not text[10].isspace():
        return False
    return True


def run(home: str, quote_scan: bool) -> int:
    root = Path(home)
    pj = root / "data" / "persistent.json"
    rp = root / "data" / "self_contradiction_report.json"

    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: 读 persistent.json 失败: {exc}", file=sys.stderr)
        return 2

    blob = collect_memory_text(data)

    if quote_scan:
        # 专门统计「技术难题 / 兜底+四方」这类历史引文的存活情况
        raw = pj.read_text(encoding="utf-8")
        hits = raw.count("技术难题") + (
            raw.count("兜底") if "四方" in raw else 0
        )
        print(f"persistent.json 命中 = {hits} 处（技术难题 或 兜底∧四方）")
        print(f"memory_blob_chars = {len(blob)}")
        return 0 if hits == 0 else 1

    try:
        report = json.loads(rp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: 读 self_contradiction_report.json 失败: {exc}", file=sys.stderr)
        return 2
    if not isinstance(report, list):
        print("ERROR: report 顶层不是 list", file=sys.stderr)
        return 2

    unresolved = [e for e in report if isinstance(e, dict) and not _is_resolved(e)]
    total_stale = 0
    print(f"report_total = {len(report)}  unresolved = {len(unresolved)}")
    print("-" * 78)
    for idx, entry in enumerate(report):
        if not isinstance(entry, dict):
            continue
        res = classify_entry(entry, blob)
        tag = "RESOLVED" if _is_resolved(entry) else "UNRESOLVED"
        flag = "STALE" if res["is_stale"] else "ok"
        if res["is_stale"] and tag == "UNRESOLVED":
            total_stale += 1
        rep = entry.get("repeat_count")
        n_abs = len(res["stale_refs"])
        print(
            f"[{idx:02d}] {tag:10s} repeat={rep if rep is not None else '-':>3} "
            f"refs={len(res['refs'])} absent={n_abs} {flag}"
        )
        for d in res["details"]:
            if d["status"] != "present":
                print(f"       ↳ {d['status']:8s} cov={d['coverage']:<6} {d['ref'][:60]}")
    print("-" * 78)
    print(f"stale_refs(未裁定且引文缺失) = {total_stale}")
    return 1 if total_stale else 0


def selftest() -> int:
    """三控：精确在 / 改写 / 已删。

    缺任一即为不及格（单向判据不合格）：
      正控 A  引文精确存在   ⇒ 不得判 stale
      正控 B  引文被改写     ⇒ 不得判 stale（防「改写误判成消失」的假阳性）
      负控    引文已删       ⇒ 必须判 stale
    """
    entry = {
        "contradiction": (
            "决策「技术难题自己想办法整理，四方只作兜底」与模式"
            "「任务消息必须真写盘产出后再回执（调研≠完成）」存在张力"
        )
    }

    # 负控：决策已删（当前真实状态）⇒ 必须判 stale
    memory_live = _norm("任务消息必须真写盘产出后再回执（调研≠完成）")
    neg = classify_entry(entry, memory_live)
    neg_ok = neg["is_stale"] and len(neg["stale_refs"]) == 1

    # 正控 A：两条引文都在 ⇒ 不得 stale
    memory_both = _norm(
        "技术难题自己想办法整理，四方只作兜底\n"
        "任务消息必须真写盘产出后再回执（调研≠完成）"
    )
    pos = classify_entry(entry, memory_both)
    pos_ok = (not pos["is_stale"]) and len(pos["refs"]) == 2

    # 正控 B：引文被改写（真实案例：交付风格那条在盘上是更长版本）⇒ 不得 stale
    # 夹具只放**一条**引文：多放会把「另一条不在夹具里」也算成 stale，测的就
    # 不是「改写能否被识别」了（11-16 首次跑时正是这个夹具错误导致假 FAIL）。
    para_entry = {"contradiction": "决策「交付风格：可逆的我定、不可逆的上收」与某模式冲突"}
    memory_para = _norm(
        "交付风格：给「建议+我负责执行到底」，可逆的我定、不可逆的上收；"
        "汇报先结论后证据；两条均须落 owner+deadline"
    )
    para = classify_entry(para_entry, memory_para)
    para_ok = not para["is_stale"]

    print(f"[正控A] 引文精确在 ⇒ absent={len(pos['stale_refs'])} refs={len(pos['refs'])} "
          f"=> {'PASS' if pos_ok else 'FAIL'}")
    print(f"[正控B] 引文被改写 ⇒ status={para['details'][0]['status'] if para['details'] else '?'} "
          f"cov={para['details'][0]['coverage'] if para['details'] else '?'} "
          f"=> {'PASS' if para_ok else 'FAIL'}")
    print(f"[负控]  引文已删   ⇒ absent={len(neg['stale_refs'])} => {'PASS' if neg_ok else 'FAIL'}")
    ok = pos_ok and para_ok and neg_ok
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="梦境蒸馏矛盾引文存在性探针（只读）")
    ap.add_argument("--home", default=DEFAULT_HOME, help="Mimir 数据根")
    ap.add_argument("--quote-scan", action="store_true",
                    help="只统计历史引文在 persistent.json 的命中数")
    ap.add_argument("--selftest", action="store_true", help="跑正/负控自测")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.home, args.quote_scan)


if __name__ == "__main__":
    sys.exit(main())
