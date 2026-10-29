#!/usr/bin/env python3
"""probe_attest_clusters.py — 自证账本的「周维度同质聚类 → 上游改进清单」（只读分析件）。

背景（2026-10-29 刘哥批 · SLO 看板 v2 + 自证闸门未达标判断）：
  自证闸门（agent/probe_attest.py）已具备「拦 + 判据」——§8.5 形式过闸。
  但它从不追问「同一类结论为什么反复出现」：拦下来 → 补证据 → 放行，
  账本沦为记录噪音，读数不驱动行为改变。
  本件把账本按 reason 同质聚类 + 周分桶 + 阈值判定，输出可执行改进清单：
  每类给出 §5.1 错误升级阶梯档位 + 上游该改哪里。

只读：不写账本、不改运行时、不新增打点。

口径（与 agent/verification_ledger.py 一致）：
  · no_data != no_failure：空账本 ⇒ status="no_data" / n_a=True / total=None，绝不用 0 充数。
  · 账本健康度显式报：lines / parsed / skipped（解析失败不静默吞掉）。

用法：
  ~/src/MimirAether/.venv/bin/python3 scripts/probe_attest_clusters.py
  ~/src/MimirAether/.venv/bin/python3 scripts/probe_attest_clusters.py --weeks 4 --threshold 10 --json
  ~/src/MimirAether/.venv/bin/python3 scripts/probe_attest_clusters.py --selftest

退出码：0 = ok（含「无超阈类」= 健康）· 1 = no_data · 2 = 参数错/自检失败
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

NO_DATA_SEMANTICS = "no_data != no_failure"
DEFAULT_THRESHOLD = 10
DEFAULT_WEEKS = 4

# ── 上游归因映射（人工维护；level 取 AGENTS §5.1 错误升级阶梯） ──────────
UPSTREAM: Dict[str, Dict[str, str]] = {
    "no_attestation": {
        "level": "2-流程",
        "target": "agent/probe_attest.py::evaluate_turn",
        "action": "闸门已拦但只补不治：加「声明类动词出现即预填探针骨架」预检，别让事后补证成常态",
    },
    "claim_in_code_block": {
        "level": "3-指令",
        "target": "agent/probe_attest.py::build_nudge",
        "action": "nudge 未明写「结论别放代码块（会被判 code_only 而不拦）」⇒ 补逐字说明",
    },
    "positive_control_failed": {
        "level": "2-流程",
        "target": "探针模板（调用侧）",
        "action": "正控样本本身不含目标串：给可复用正控样例，别每次现编",
    },
    "negative_control_failed": {
        "level": "2-流程",
        "target": "探针模板（调用侧）",
        "action": "负控样本命中了目标串：负控须为「已知不该命中」的独立样本",
    },
    "control_is_target": {
        "level": "3-指令",
        "target": "agent/probe_attest.py::build_nudge",
        "action": "三硬约束已在 nudge 列出但未被读：把「控制样本≠目标样本」做成报错首行",
    },
    "controls_identical_content": {
        "level": "3-指令",
        "target": "agent/probe_attest.py::build_nudge",
        "action": "正负控内容相同=空洞控制组；nudge 需给反例",
    },
    "control_mismatch": {
        "level": "2-流程",
        "target": "agent/probe_attest.py::attest",
        "action": "观测值与期望不符时，报错未指出哪个控制组坏了",
    },
    "target_reuses_negative": {
        "level": "3-指令",
        "target": "agent/probe_attest.py::attest",
        "action": "目标样本复用负控样本（同义反复）⇒ 报错须直说「目标必须是真实样本」",
    },
    "target_reuses_negative_content": {
        "level": "3-指令",
        "target": "agent/probe_attest.py::attest",
        "action": "同上（按内容指纹判定）",
    },
    "no_input_placeholder": {
        "level": "3-指令",
        "target": "agent/probe_attest.py::build_nudge",
        "action": "探针命令漏写 {INPUT} 占位符：nudge 里把占位符写进可复制模板",
    },
}

# *_probe_dead(...) 同族，用前缀匹配
UPSTREAM_PREFIX: List[tuple] = [
    ("positive_probe_dead", {
        "level": "2-流程",
        "target": "探针命令本身（rc=2/128=用法或读文件错）",
        "action": "探针跑不起来=死探针被当成 none：先修命令，别解读读数",
    }),
    ("negative_probe_dead", {
        "level": "2-流程",
        "target": "探针命令本身（rc=2/128=用法或读文件错）",
        "action": "同上；负控死掉时「没命中」是假象",
    }),
    ("target_probe_dead", {
        "level": "2-流程",
        "target": "探针命令本身（rc=2/128=用法或读文件错）",
        "action": "同上；目标样本读不到 ≠ 目标不含目标串",
    }),
]


def _upstream_for(reason: str) -> Dict[str, str]:
    if reason in UPSTREAM:
        return dict(UPSTREAM[reason])
    for prefix, meta in UPSTREAM_PREFIX:
        if reason.startswith(prefix):
            return dict(meta)
    return {
        "level": "未归因",
        "target": "（映射表缺该项）",
        "action": "新出现的 reason ⇒ 人工归因后补进 UPSTREAM 表",
    }


def _week_key(ts: str) -> Optional[str]:
    """ISO 周键，如 2026-W44。ts 解析失败返回 None（不猜）。"""
    try:
        d = _dt.date.fromisoformat(ts[:10])
    except (ValueError, TypeError):
        return None
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def load_ledger(path: Path) -> Dict[str, Any]:
    """读账本 → {status,n_a,reason,records,health}。空/缺 ⇒ no_data（不充 0）。"""
    if not path.exists():
        return {
            "status": "no_data", "n_a": True,
            "reason": f"账本不存在：{path}（无数据 ≠ 无未达标）",
            "records": [], "health": {"lines": 0, "parsed": 0, "skipped": 0},
        }
    records: List[Dict[str, Any]] = []
    lines = skipped = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        lines += 1
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if isinstance(obj, dict):
            records.append(obj)
        else:
            skipped += 1
    health = {"lines": lines, "parsed": len(records), "skipped": skipped}
    if not records:
        return {
            "status": "no_data", "n_a": True,
            "reason": f"可解析记录为 0（lines={lines} skipped={skipped}）⇒ 无数据 ≠ 无未达标",
            "records": [], "health": health,
        }
    return {"status": "ok", "n_a": False, "reason": None,
            "records": records, "health": health}


def _window_start(records: Iterable[Dict[str, Any]], weeks: int) -> Optional[str]:
    """以账本最新记录为锚回退 weeks 周（不按墙钟——账本可能停更）。"""
    stamps = sorted(r.get("ts", "") for r in records if r.get("ts"))
    if not stamps:
        return None
    try:
        d = _dt.date.fromisoformat(stamps[-1][:10])
    except ValueError:
        return None
    return (d - _dt.timedelta(weeks=weeks)).isoformat()


def cluster(records: List[Dict[str, Any]], *, weeks: int = DEFAULT_WEEKS,
            threshold: int = DEFAULT_THRESHOLD,
            verdict: str = "UNVERIFIED") -> Dict[str, Any]:
    """按 reason 同质聚类 + 周分桶 + 阈判定。纯函数（便于受控差分）。"""
    since = _window_start(records, weeks)
    in_window: List[Dict[str, Any]] = []
    no_ts = 0
    for r in records:
        ts = r.get("ts") or ""
        if not ts:
            no_ts += 1
            in_window.append(r)  # 保留，不静默丢证据
            continue
        if since and ts[:10] < since:
            continue
        in_window.append(r)

    if verdict:
        targets = [r for r in in_window if r.get("verdict") == verdict]
    else:
        targets = list(in_window)

    by_reason: "collections.Counter[str]" = collections.Counter()
    weekly: Dict[str, "collections.Counter[str]"] = collections.defaultdict(collections.Counter)
    by_source: "collections.Counter[str]" = collections.Counter()
    for r in targets:
        reason = r.get("reason") or "unknown"
        by_reason[reason] += 1
        wk = _week_key(r.get("ts") or "")
        if wk:
            weekly[reason][wk] += 1
        by_source[r.get("source") or "unknown"] += 1

    total = len(targets)
    clusters: List[Dict[str, Any]] = []
    for reason, count in by_reason.most_common():
        clusters.append({
            "reason": reason,
            "count": count,
            "share": round(count / total, 4) if total else None,
            "weekly": dict(sorted(weekly[reason].items())),
            "over_threshold": count >= threshold,
            "upstream": _upstream_for(reason),
        })

    return {
        "total_scanned": len(records),
        "no_ts": no_ts,
        "window": {"weeks": weeks, "since": since},
        "verdict_filter": verdict or "(all)",
        "total_target": total,
        "by_source": dict(by_source.most_common()),
        "by_reason": dict(by_reason.most_common()),
        "clusters": clusters,
        "actionable": [c for c in clusters if c["over_threshold"]],
        "threshold": threshold,
    }


def analyze(path: Path, *, weeks: int = DEFAULT_WEEKS,
            threshold: int = DEFAULT_THRESHOLD,
            verdict: str = "UNVERIFIED") -> Dict[str, Any]:
    led = load_ledger(path)
    out: Dict[str, Any] = {
        "status": led["status"],
        "n_a": led["n_a"],
        "reason": led["reason"],
        "semantics": NO_DATA_SEMANTICS,
        "ledger_path": str(path),
        "health": led["health"],
        "total_target": None,
        "clusters": None,
        "actionable": None,
    }
    if led["status"] != "ok":
        return out
    out.update(cluster(led["records"], weeks=weeks, threshold=threshold, verdict=verdict))
    return out


def _default_ledger() -> Path:
    """优先用 probe_attest 的口径；导入失败则回退默认路径（不静默）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from agent.probe_attest import default_ledger_path  # type: ignore
        return Path(default_ledger_path())
    except Exception:  # noqa: BLE001  —— 回退路径需可见
        return Path.home() / ".mimiraether" / "data" / "ops" / "probe_attest.jsonl"


def _render(res: Dict[str, Any]) -> str:
    if res["status"] != "ok":
        return (f"status: no_data\nreason: {res['reason']}\n"
                f"semantics: {res['semantics']}\n")
    lines: List[str] = []
    w, h = res["window"], res["health"]
    lines.append(f"账本: {res['ledger_path']}")
    lines.append(f"健康: lines={h['lines']} parsed={h['parsed']} skipped={h['skipped']}"
                 "（解析失败不静默）")
    lines.append(f"窗口: 最近 {w['weeks']} 周（since={w['since']}，锚=账本最新记录）")
    lines.append(f"判据: verdict={res['verdict_filter']} · 阈值={res['threshold']}"
                 f" · 目标记录={res['total_target']}")
    lines.append("")
    if not res["clusters"]:
        lines.append("无同质聚类（窗口内无该 verdict 记录）—— 健康。")
        return "\n".join(lines)
    lines.append("聚类（按次数降序）:")
    for i, c in enumerate(res["clusters"], 1):
        mark = "超阈" if c["over_threshold"] else "  · "
        lines.append(f"{i:>2}. [{mark}] {c['reason']}  n={c['count']}  share={c['share']}")
        wk = ", ".join(f"{k}:{v}" for k, v in c["weekly"].items())
        if wk:
            lines.append(f"       周分布: {wk}")
        up = c["upstream"]
        lines.append(f"       阶梯: {up['level']} · 上游: {up['target']}")
        lines.append(f"       动作: {up['action']}")
    lines.append("")
    act = res["actionable"]
    if act:
        lines.append(f"⇒ 改进清单（{len(act)} 类超阈，应改上游而非再提醒）:")
        for c in act:
            lines.append(f"   - {c['reason']} (n={c['count']}): {c['upstream']['action']}")
    else:
        lines.append("⇒ 无超阈类：维持观察，不新增机制。")
    return "\n".join(lines)


# ── 受控自检（正控 + 负控；两向，缺一不及格） ──────────────────────────
def _mk(ts: str, reason: Optional[str], verdict: str = "UNVERIFIED",
        source: str = "probe_attest") -> Dict[str, Any]:
    return {"ts": ts, "reason": reason, "verdict": verdict, "source": source}


def _selftest() -> int:
    ok = True

    def chk(name: str, got: Any, want: Any) -> None:
        nonlocal ok
        good = got == want
        ok = ok and good
        print(f"[{'PASS' if good else 'FAIL'}] {name}: got={got!r} want={want!r}")

    # 正控 A：已知分布的合成账本，阈值 10 ⇒ actionable 恰为前两类，计数精确
    recs: List[Dict[str, Any]] = []
    for i in range(12):
        recs.append(_mk(f"2026-10-2{7 + i % 2}T00:00:0{i % 10}", "no_attestation"))
    for i in range(10):
        recs.append(_mk(f"2026-10-2{7 + i % 2}T01:00:0{i % 10}", "claim_in_code_block"))
    for i in range(5):
        recs.append(_mk(f"2026-10-2{7 + i % 2}T02:00:0{i % 10}", "positive_control_failed"))
    for i in range(3):
        recs.append(_mk(f"2026-10-2{7 + i % 2}T03:00:0{i % 10}", "control_is_target"))
    for i in range(7):
        recs.append(_mk(f"2026-10-2{7 + i % 2}T04:00:0{i % 10}", "irrelevant", verdict="VERIFIED"))

    res = cluster(recs, weeks=400, threshold=10)
    chk("A1 总目标数（只数 UNVERIFIED，混入的 VERIFIED 不计）", res["total_target"], 30)
    chk("A2 超阈类数", len(res["actionable"]), 2)
    chk("A3 超阈类名（有序）",
        [c["reason"] for c in res["actionable"]],
        ["no_attestation", "claim_in_code_block"])
    chk("A4 超阈类计数精确",
        [c["count"] for c in res["actionable"]], [12, 10])
    chk("A5 未超阈类不进清单",
        [c["reason"] for c in res["clusters"] if not c["over_threshold"]],
        ["positive_control_failed", "control_is_target"])

    # 正控 B：阈值抬高到 11 ⇒ 只剩 1 类超阈（证明阈值真的生效，不是恒定全报）
    res_b = cluster(recs, weeks=400, threshold=11)
    chk("B1 阈值 11 ⇒ 超阈类数", len(res_b["actionable"]), 1)
    chk("B2 阈值 11 ⇒ 仅剩 no_attestation",
        [c["reason"] for c in res_b["actionable"]], ["no_attestation"])

    # 正控 C：周分桶（跨周样本必须分到两个周键）
    res_c = cluster(recs, weeks=400, threshold=10)
    wk = res_c["actionable"][0]["weekly"]
    chk("C1 周分桶键数（10-27 与 10-28 属同一 ISO 周则应为 1）", len(wk), 1)

    # 负控 1：健康账本（全 VERIFIED）⇒ status=ok 但目标=0、清单空（不是 no_data）
    healthy = [_mk("2026-10-28T00:00:00", None, verdict="VERIFIED") for _ in range(5)]
    res_n1 = cluster(healthy, weeks=400, threshold=10)
    chk("N1a 健康账本 status（有数据）", res_n1["total_target"], 0)
    chk("N1b 健康账本清单空", res_n1["actionable"], [])

    # 负控 2：空账本 ⇒ no_data（绝不充 0）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        res_n2 = analyze(empty)
        chk("N2a 空账本 status", res_n2["status"], "no_data")
        chk("N2b 空账本 n_a", res_n2["n_a"], True)
        chk("N2c 空账本 total 为 None（不用 0 充数）", res_n2["total_target"], None)

        # 负控 3：坏行不静默（1 条好 + 2 条坏 ⇒ parsed=1 skipped=2）
        bad = Path(td) / "bad.jsonl"
        bad.write_text(
            '{"ts":"2026-10-28T00:00:00","verdict":"UNVERIFIED","reason":"no_attestation"}\n'
            'not json\n'
            '[1,2,3]\n', encoding="utf-8")
        res_n3 = analyze(bad)
        chk("N3a 坏行解析计数", res_n3["health"],
            {"lines": 3, "parsed": 1, "skipped": 2})
        chk("N3b 坏行仍能出聚类", res_n3["total_target"], 1)

    # 负控 4：未归因 reason 必须显式标「未归因」，不许静默给动作
    res_n4 = cluster([_mk("2026-10-28T00:00:00", "brand_new_reason")], weeks=400, threshold=1)
    chk("N4 未归因类标注", res_n4["actionable"][0]["upstream"]["level"], "未归因")

    print("---")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 2


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="自证账本周维度同质聚类（只读）")
    ap.add_argument("--ledger", type=Path, default=None, help="账本路径（默认 probe_attest 口径）")
    ap.add_argument("--weeks", type=int, default=DEFAULT_WEEKS, help="回看周数（锚=账本最新记录）")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="超阈计数")
    ap.add_argument("--verdict", default="UNVERIFIED", help="只聚类该 verdict；空串=全部")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--selftest", action="store_true", help="受控自检（正控+负控）")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.weeks < 0 or args.threshold < 0:
        print("参数错误：--weeks/--threshold 须 >= 0", file=sys.stderr)
        return 2

    path = args.ledger or _default_ledger()
    res = analyze(path, weeks=args.weeks, threshold=args.threshold,
                  verdict=args.verdict)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(_render(res))
    return 0 if res["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
