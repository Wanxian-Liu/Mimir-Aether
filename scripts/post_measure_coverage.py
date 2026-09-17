"""H2 覆盖度报告：`applied` 里有多少真的拿到了 post 实计（结算率）。

背景（2026-09-17）：`applied 78 / post_measure 1` ⇒ 结算率 **1.3%** —— 真因是
`gateway/platforms/api_server.py:1538` 在 `_run_agent()` 体内建 agent，每 run 一个
新 compressor ⇒ 挂账是**实例字段** ⇒ 跨 run 结算结构上不可能。H2 加了跨 run
持久化 ⇒ **本脚本是它的效果度量**（没有度量就不许说「修好了」）。

口径（写进输出，防下次误读）：
  · `applied`  = 真正落地的压缩（`outcome == "applied"` 且非 `kind=post_measure` 行）
  · `settled`  = 拿到 post 实计的（`settle_reason == "settled"`）
  · 覆盖率     = settled / applied
  · `settle_source`：`same_run` / `cross_run` / `pre_h2`（字段缺失 = H2 之前的历史行）
  · `abandoned`  = **N4（2026-09-18）「未交未出谁认账」**：认领凭据存在、但**没有任何
    post_measure 行**携带同一 `claim_corr_id`，且已过 grace ⇒ 这笔账**认了却没人交**。
    正常路径恒 0；>0 即 FAIL（显式，不静默）。

用法：`.venv/bin/python3 scripts/post_measure_coverage.py [--min-coverage 0.5] [--json]`
退出码：0 = 达标；1 = 未达标；2 = **目标文件不存在**（显式失败，不静默返 0）。
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

# 与 scripts/ 下同族脚本一致：本文件直接跑时 sys.path[0] 是 scripts/，
# 不注入 repo 根就 import 不到 mimir_constants（**首版就栽在这**：import 失败被
# `except` 吞掉 ⇒ 悄悄退回相对路径 ⇒ 报「file not found」而真因是 import 错）。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_home  # noqa: E402

PRE_H2 = "pre_h2"
# N4：认领凭据目录（与 agent/context_compressor.py 的 _CLAIM_STORE_DIRS 同源）
CLAIM_DIRS = ("data", "ops", "pending_post_measure_claims")
DEFAULT_ABANDON_GRACE_S = 3600.0


def load_rows(path):
    rows, bad = [], 0
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                bad += 1
    return rows, bad


def load_claim_rows(dirpath):
    """读认领凭据。**目录不存在 ⇒ 空**（H2/N4 之前的历史环境，不是错误）。"""
    d = Path(dirpath)
    rows, bad = [], 0
    if not d.is_dir():
        return rows, bad
    for p in sorted(d.glob("*.json")):
        try:
            rows.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            bad += 1
    return rows, bad


def claims_report(claim_rows, matched_ids, now=None, grace_s=DEFAULT_ABANDON_GRACE_S):
    """把「认领 but 无结算行」拆成两类 —— 不许混成一个数（混了就分不清在途 vs 真丢）。

    · 已过 grace ⇒ ``abandoned``（认了账、人/进程没了）—— 真问题，要显式可见
    · 未过 grace ⇒ ``claims_inflight``（刚认领、还没到结算点）—— 正常在途
    """
    now = time.time() if now is None else now
    abandoned, inflight, matched = [], [], 0
    for c in claim_rows:
        cid = str(c.get("corr_id") or "")
        if cid and cid in matched_ids:
            matched += 1
            continue
        try:
            age = max(0.0, now - float(c.get("claimed_at") or 0))
        except Exception:
            age = None
        item = {
            "corr_id": cid or None,
            "claimed_at_iso": c.get("claimed_at_iso"),
            "pid": c.get("pid"),
            "session_tag": c.get("session_tag"),
            "age_s": (round(age, 1) if age is not None else None),
        }
        if age is not None and age > grace_s:
            abandoned.append(item)
        else:
            inflight.append(item)
    return {
        "claims_total": len(claim_rows),
        "claims_matched": matched,
        "abandoned": len(abandoned),
        "claims_inflight": len(inflight),
        "abandon_grace_s": grace_s,
        "abandoned_detail": abandoned[:10],
        "inflight_detail": inflight[:10],
    }


def analyze(rows):
    applied = 0
    post = []
    for r in rows:
        if r.get("kind") == "post_measure":
            post.append(r)
        elif r.get("outcome") == "applied":
            applied += 1
    reasons = Counter(str(r.get("settle_reason")) for r in post)
    sources = Counter(str(r.get("settle_source") or PRE_H2) for r in post)
    settled = reasons.get("settled", 0)
    coverage = (settled / applied) if applied else None
    return {
        "applied": applied,
        "post_rows": len(post),
        "settled": settled,
        "coverage": coverage,
        "settle_reasons": dict(reasons),
        "settle_sources": dict(sources),
        "unsettled": applied - settled,
        # N4：结算行自报的关联 id（用于跟认领凭据对账）
        "_matched_claim_ids": {str(r.get("claim_corr_id")) for r in post
                               if r.get("claim_corr_id")},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="H2 post-measure coverage")
    ap.add_argument("--ledger", default=None, help="台账路径（默认走真源 mimir home）")
    ap.add_argument("--min-coverage", type=float, default=0.5)
    ap.add_argument("--claims-dir", default=None,
                    help="认领凭据目录（默认走真源 mimir home 的 data/ops/pending_post_measure_claims）")
    ap.add_argument("--abandon-grace-s", type=float, default=DEFAULT_ABANDON_GRACE_S,
                    help="未结算凭据超过该秒数才判 abandoned（之内算在途）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = (Path(args.ledger) if args.ledger
            else get_mimir_home() / "data" / "compression_quality.jsonl")

    if not path.exists():
        print("FAIL: compression_quality.jsonl not found: %s" % path)
        return 2

    rows, bad = load_rows(path)
    s = analyze(rows)
    _matched = s.pop("_matched_claim_ids", set())
    _claims_dir = (Path(args.claims_dir) if args.claims_dir
                   else get_mimir_home() / Path(*CLAIM_DIRS))
    _claim_rows, _claim_bad = load_claim_rows(_claims_dir)
    s.update(claims_report(_claim_rows, _matched, grace_s=args.abandon_grace_s))
    s["claims_dir"] = str(_claims_dir)
    s["claims_unparsable"] = _claim_bad
    s["ledger"] = str(path)
    s["unparsable_lines"] = bad

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        _cov_ok = (s["coverage"] is not None and s["coverage"] >= args.min_coverage)
        return 0 if (_cov_ok and s["abandoned"] == 0) else 1

    print("ledger      : %s" % s["ledger"])
    print("applied     : %d" % s["applied"])
    print("post rows   : %d  (settled=%d / 未结=%d)"
          % (s["post_rows"], s["settled"], s["unsettled"]))
    print("reasons     : %s" % (s["settle_reasons"] or "{}"))
    print("sources     : %s" % (s["settle_sources"] or "{}"))
    print("coverage    : %s" % ("n/a" if s["coverage"] is None
                                else "%.4f (min=%.2f)" % (s["coverage"], args.min_coverage)))
    print("claims      : total=%d matched=%d inflight=%d ABANDONED=%d (grace=%ss)"
          % (s["claims_total"], s["claims_matched"], s["claims_inflight"],
             s["abandoned"], int(s["abandon_grace_s"])))
    for _d in s["abandoned_detail"]:
        print("  ABANDONED  : corr_id=%s pid=%s session=%s age=%ss claimed=%s"
              % (_d["corr_id"], _d["pid"], _d["session_tag"], _d["age_s"],
                 _d["claimed_at_iso"]))
    if s["claims_unparsable"]:
        print("CLAIMS_BAD  : %d 个凭据不可解析" % s["claims_unparsable"])
    if bad:
        print("UNPARSABLE  : %d line(s)" % bad)
    if s["applied"] == 0:
        print("VERDICT: NO_APPLIED -- 没有 applied 行，覆盖率无从计算")
        return 1
    if s["abandoned"] > 0:
        # N4：**先于** 覆盖率判 —— 「认了账没人交」是比「率低」更硬的失败。
        print("VERDICT: ABANDONED -- %d 笔认领凭据无对应结算行（未交未出）；"
              "见上面 ABANDONED 明细" % s["abandoned"])
        return 1
    if s["coverage"] >= args.min_coverage:
        print("VERDICT: OK")
        return 0
    print("VERDICT: LOW -- 结算率低于下限；先看 sources 里 cross_run 是否为 0")
    return 1


if __name__ == "__main__":
    sys.exit(main())
