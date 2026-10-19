#!/usr/bin/env python3
"""watermark_reconcile.py — S3′ 水位线判据「能红」对账器（**只读**）.

规格真源：会议卡 `2026-10-13-四方会议-既往审计×L5重构×知识库统一.md` §B S3′ 六栏（L900–911）。
角色卡规则来源：RAG Pipeline Engineer L59（never skip evals · before/after 读数）·
L450（weekly drift report · 平均 top-1 相似度下降 ⇒ 语料/查询分布漂移）。

判据（三条，缺一不算过）：
  正控    同输入重跑 ⇒ `n` **不变** ∧ `digest` **不变** ⇒ rc=0
  负控① 同输入重跑时 `n` **增长**（喂入新内容）⇒ 必须 FAIL（rc=1）
  负控② 删掉 `digest` 键后重跑 ⇒ 必须**全量重跑**（`prefix_len == 0`）；仍走增量 ⇒ FAIL

反例边界（本席 R1b 自写，本脚本已落）：
  某会话本轮**真的新增 0 块**时 `n` 不变是**真绿** ⇒ 判据必须**带分母** `scanned>0` 才闭合。
  故：`scanned == 0` ⇒ rc=2（不可判定，禁当绿）。

只读保证：本脚本**绝不**写 `index_watermark.json` 本体；负控一律作用于 `--wm` 指向的**副本**。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO))
try:
    from tools.session_search_indexer import messages_digest as _prod_digest  # type: ignore
except Exception:  # pragma: no cover - 回退：同口径本地复刻
    _prod_digest = None


def _fallback_digest(messages: List[Dict[str, Any]], upto: Optional[int] = None) -> str:
    h = hashlib.sha256()
    seq = messages if upto is None else list(messages)[:upto]
    for m in seq:
        if isinstance(m, dict):
            key = (m.get("role"), m.get("content"), m.get("tool_name"))
        else:
            key = None
        h.update(repr(key).encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def digest_of(messages: List[Dict[str, Any]], upto: Optional[int] = None) -> str:
    if _prod_digest is not None:
        return _prod_digest(messages, upto)
    return _fallback_digest(messages, upto)


def _data_home() -> Path:
    """解析数据根 —— 沙箱 HOME 与生产 HOME 不同 ⇒ 禁裸 Path.home()（2026-10-13 实测踩坑）。"""
    try:
        from mimir_constants import get_mimir_home  # type: ignore

        return Path(get_mimir_home())
    except Exception:
        import os

        return Path(
            os.environ.get("MIMIR_AETHER_HOME")
            or os.environ.get("MIMIR_HOME")
            or (REPO.parent.parent / ".mimiraether")
        )


def _default_wm() -> Path:
    return _data_home() / "data" / "index_watermark.json"


def _sessions_dir() -> Path:
    return _data_home() / "data" / "sessions"


DEFAULT_WM = _default_wm()


def load_real_messages(session_id: str, sessions_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """读**真实**会话 transcript（*.jsonl）——判据必须打在生产输入上。

    ⚠️ 反例（本席 2026-10-13 实测踩到）：用「合成消息」重算 digest ⇒ 5/5 全 mismatch，
    那是**输入不是真输入**的假红，不是水位线坏了。⇒ 判据的输入面 = 生产会话文件。
    """
    d = sessions_dir or _sessions_dir()
    p = d / f"{session_id}.jsonl"
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def load_wm(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


GLOBAL_KEYS = ("n", "digest", "ts")


def session_records(wm: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """会话级记录——剔除全局三键 n/digest/ts 与非 dict 值。

    为什么必须过滤：`scan()`/`sid` 选择都做 `rec.get()`，全局键是标量，
    不过滤即 AttributeError（旧读端遇到新 schema 会崩，这是「加字段」的必修面）。
    """
    return {k: v for k, v in wm.items() if k not in GLOBAL_KEYS and isinstance(v, dict)}


def assert_global(wm: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """落盘判据：全局三键 n/digest/ts 齐 ∧ 类型正确 ⇒ rc=0；否则 rc=1。"""
    missing = [k for k in GLOBAL_KEYS if k not in wm]
    bad: List[str] = []
    if "n" in wm and not isinstance(wm["n"], int):
        bad.append("n:not-int")
    if "digest" in wm and not (isinstance(wm["digest"], str) and len(wm["digest"]) == 32):
        bad.append("digest:not-32hex")
    if "ts" in wm and not isinstance(wm["ts"], (int, float)):
        bad.append("ts:not-number")
    ok = not missing and not bad
    return (0 if ok else 1), {
        "missing": missing,
        "type_violations": bad,
        "n": wm.get("n"),
        "digest": str(wm.get("digest"))[:8],
        "ts": wm.get("ts"),
        "sessions": len(session_records(wm)),
    }


def prefix_len(rec: Dict[str, Any], messages: List[Dict[str, Any]]) -> int:
    """与 tools/session_search_indexer.watermark_prefix_len 同语义（只读复刻）。

    0 = 前缀变了/未知 ⇒ 索引器会**全量重跑**；>0 = 可复用的增量前缀条数。
    """
    n = int(rec.get("n") or 0)
    if n <= 0 or n > len(messages):
        return 0
    if digest_of(messages, n) != rec.get("digest"):
        return 0
    return n


def scan(wm: Dict[str, Any], sessions_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """逐会话取真实 transcript ⇒ 复算 digest + prefix_len（**只读**）。"""
    rows: List[Dict[str, Any]] = []
    for sid in sorted(session_records(wm)):
        rec = wm.get(sid) or {}
        n = int(rec.get("n") or 0)
        msgs = load_real_messages(sid, sessions_dir)
        if not msgs:
            rows.append({"session": sid, "n": n, "file_msgs": 0, "file_exists": False})
            continue
        recomputed = digest_of(msgs, n) if n > 0 else None
        pl = prefix_len(rec, msgs)
        rows.append({
            "session": sid,
            "n": n,
            "file_exists": True,
            "file_msgs": len(msgs),
            "stored_digest": rec.get("digest"),
            "recomputed_digest": recomputed,
            "digest_match": recomputed == rec.get("digest"),
            "prefix_len": pl,
            "incremental_ok": (pl == n) and n > 0,
        })
    return rows


def criterion_incremental(wm: Dict[str, Any], sessions_dir: Optional[Path] = None) -> Tuple[int, Dict[str, Any]]:
    """正控：同输入重跑 ⇒ `n` 不变 ∧ `digest` 不变（前缀仍可复用）⇒ rc=0。

    分母：`scanned` = 真正取到 transcript 的会话数；`scanned == 0` ⇒ rc=2（不可判定，**禁当绿**）。
    """
    rows = scan(wm, sessions_dir)
    scanned = sum(1 for r in rows if r.get("file_exists"))
    bad = [r for r in rows if r.get("file_exists") and not r.get("incremental_ok")]
    if scanned == 0:
        return 2, {"scanned": 0, "rows": rows, "reason": "scanned=0 ⇒ 不可判定（禁当绿）"}
    return (1 if bad else 0), {"scanned": scanned, "rows": rows, "mismatch": len(bad)}


def compare_runs(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """「同输入重跑」的判据核：`n` 不变 ∧ `digest` 不变 ⇒ PASS；任一变动 ⇒ FAIL。"""
    n_same = int(before.get("n") or 0) == int(after.get("n") or 0)
    d_same = before.get("digest") == after.get("digest")
    return (0 if (n_same and d_same) else 1), {
        "n_before": before.get("n"), "n_after": after.get("n"),
        "digest_before": str(before.get("digest"))[:8], "digest_after": str(after.get("digest"))[:8],
        "n_same": n_same, "digest_same": d_same,
    }


def neg_control_growth(wm: Dict[str, Any], sid: str, sessions_dir: Optional[Path] = None) -> Tuple[int, Dict[str, Any]]:
    """负控①：同输入重跑时 `n` **增长**（喂入新内容）⇒ 判据必须报 FAIL。

    注入方式 = 只改记录里的 `n`（输入消息**逐字不动**）⇒ 模拟「同输入被重复计入」的增量失效。
    通过条件 = 判据**察觉到**（rc=1 = detected），察觉不到才是不合格。
    """
    rec = dict(wm.get(sid) or {})
    msgs = load_real_messages(sid, sessions_dir)
    grown = dict(rec)
    grown["n"] = int(rec.get("n") or 0) + 8
    if msgs:
        grown["digest"] = digest_of(msgs, grown["n"])
    rc, det = compare_runs(rec, grown)
    ok = rc == 1
    return (0 if ok else 1), {
        "control_ok": ok,
        "judge_verdict": "FAIL" if ok else "PASS(判据失灵·假绿)",
        "judge_rc": rc,
        **det,
    }


def neg_control_missing_digest(wm: Dict[str, Any], sid: str, sessions_dir: Optional[Path] = None) -> Tuple[int, Dict[str, Any]]:
    """负控②：删 `digest` 键 ⇒ 必须**全量重跑**（`prefix_len == 0`）；仍走增量 ⇒ FAIL。"""
    rec = dict(wm.get(sid) or {})
    n = int(rec.get("n") or 0)
    msgs = load_real_messages(sid, sessions_dir)
    stripped = {k: v for k, v in rec.items() if k != "digest"}
    pl = prefix_len(stripped, msgs) if msgs else None
    ok = pl == 0
    return (0 if ok else 1), {
        "control_ok": ok,
        "judge_verdict": "FULL-REINDEX(全量重跑·符合预期)" if ok else "INCREMENTAL(判据失灵·假绿)",
        "judge_rc": 0 if ok else 1,
        "n": n,
        "digest_key_present": "digest" in stripped,
        "prefix_len": pl,
        "file_msgs": len(msgs),
    }


HISTORY_DEFAULT = _data_home() / "data" / "p0_index_health_history.jsonl"
SIMILARITY_KEYS = ("avg_top1_similarity", "top1_similarity", "avg_top1_sim", "top1_sim")
DRIFT_DROP_THRESHOLD = 0.05  # 相对下降 >5% ⇒ 报警（角色卡 L450）


def drift_report(history: Optional[Path] = None, window_days: int = 7,
                 threshold: float = DRIFT_DROP_THRESHOLD) -> Tuple[int, Dict[str, Any]]:
    """漂移闸（角色卡 L450）：周报比平均 top-1 相似度，下降超阈 ⇒ 报警。

    **复用既有报告面** `data/p0_index_health_history.jsonl`（零新建机制/零新建文件）。
    rc=0 无漂移 · rc=1 漂移超阈（报警）· rc=2 **数据面缺失**（不可判定 —— 禁当绿）。
    """
    p = history or HISTORY_DEFAULT
    if not p.exists():
        return 2, {"reason": f"history 面缺失: {p}"}
    recs: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except Exception:
            continue
    with_sim = [r for r in recs if any(k in r for k in SIMILARITY_KEYS)]
    if not with_sim:
        # 诚实出口：相似度留痕面不存在 ⇒ **不编数字**（禁「缺列当绿」）
        return 2, {
            "reason": "无 top-1 相似度留痕字段 ⇒ 不可判定（角色卡 L450 的前置面未建）",
            "similarity_keys_probed": list(SIMILARITY_KEYS),
            "history_rows": len(recs),
            "available_axes": sorted({k for r in recs for k in r}),
        }

    def _val(r: Dict[str, Any]) -> float:
        for k in SIMILARITY_KEYS:
            if k in r:
                return float(r[k])
        return float("nan")

    with_sim.sort(key=lambda r: str(r.get("checked_at") or ""))
    cur = [_val(r) for r in with_sim[-window_days:]]
    prev = [_val(r) for r in with_sim[-2 * window_days:-window_days]]
    if not prev:
        return 2, {"reason": "窗口不足（无上一个周窗可比）", "rows_with_similarity": len(with_sim)}
    cur_avg, prev_avg = sum(cur) / len(cur), sum(prev) / len(prev)
    rel = (cur_avg - prev_avg) / prev_avg if prev_avg else 0.0
    alert = rel < -threshold
    return (1 if alert else 0), {
        "window_days": window_days, "threshold": threshold,
        "prev_avg_top1": round(prev_avg, 6), "cur_avg_top1": round(cur_avg, 6),
        "rel_change": round(rel, 6), "alert": alert,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="S3′ 水位线判据对账（只读 · 复用生产 digest 口径）")
    ap.add_argument("--wm", default=str(DEFAULT_WM), help="水位线文件（负控请指向副本）")
    ap.add_argument("--session", default=None, help="指定会话键（默认全部）")
    ap.add_argument("--mode", choices=["reconcile", "neg-growth", "neg-nodigest", "drift"],
                    default="reconcile")
    ap.add_argument("--history", default=None, help="漂移闸的历史面（负控请指向副本）")
    ap.add_argument("--assert-global", action="store_true",
                    help="落盘判据：断言 index_watermark.json 全局三键 n/digest/ts 齐")
    ap.add_argument("--selftest", action="store_true", help="三判据 + 漂移闸自测（不碰生产件）")
    args = ap.parse_args(argv)

    wm_path = Path(args.wm)
    if not wm_path.exists():
        print(f"VERDICT: FAIL (rc=2) — watermark file not found: {wm_path}")
        return 2
    wm = load_wm(wm_path)
    if not wm:
        print("VERDICT: FAIL (rc=2) — watermark empty ⇒ scanned=0 不可判定")
        return 2

    if args.assert_global:
        rc, r = assert_global(wm)
        print(json.dumps({"mode": "assert-global", "rc": rc, **r}, ensure_ascii=False, indent=2))
        print(f"VERDICT: {'PASS' if rc == 0 else 'FAIL'} (rc={rc})")
        return rc

    recs = session_records(wm)
    if not recs:
        print("VERDICT: FAIL (rc=2) — 无会话级记录 ⇒ 不可判定")
        return 2
    sid = args.session or max(recs, key=lambda k: int((recs[k] or {}).get("n") or 0))

    if args.selftest:
        rc1, r1 = criterion_incremental(wm)
        rc2, r2 = neg_control_growth(wm, sid)
        rc3, r3 = neg_control_missing_digest(wm, sid)
        rcd, rd = drift_report(Path(args.history) if args.history else None)
        print(f"正控   reconcile    rc={rc1} scanned={r1['scanned']} mismatch={r1.get('mismatch', '-')}")
        print(f"负控① neg-growth   rc={rc2} judge={r2.get('judge_verdict')} n {r2.get('n_before')}→{r2.get('n_after')}")
        print(f"负控② neg-nodigest rc={rc3} judge={r3.get('judge_verdict')} prefix_len={r3.get('prefix_len')}")
        print(f"漂移闸 drift        rc={rcd} {rd.get('reason') or rd}")
        allok = rc1 == 0 and rc2 == 0 and rc3 == 0
        print(f"VERDICT: {'PASS' if allok else 'FAIL'} (selftest rc={0 if allok else 1}; 漂移闸 rc={rcd} 单列)")
        return 0 if allok else 1

    if args.mode == "reconcile":
        rc, r = criterion_incremental(wm) if not args.session else (
            lambda rows: (0 if rows[0].get("incremental_ok") else 1, {"scanned": 1, "rows": rows}))(
                [x for x in scan(wm) if x["session"] == sid])
    elif args.mode == "neg-growth":
        rc, r = neg_control_growth(wm, sid)
    elif args.mode == "neg-nodigest":
        rc, r = neg_control_missing_digest(wm, sid)
    else:
        rc, r = drift_report(Path(args.history) if args.history else None)

    print(json.dumps({"mode": args.mode, "session": sid, "rc": rc, **r}, ensure_ascii=False, indent=2))
    print(f"VERDICT: {'PASS' if rc == 0 else ('UNDECIDABLE' if rc == 2 else 'FAIL')} (rc={rc})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
