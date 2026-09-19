#!/usr/bin/env python3
"""B1/B3 记账回填：给已停用的 cron job 补 disable_reason（2026-09-19 · 刘哥批）。

为什么需要一次性回填：
    `check_cron_hygiene.py` 的 R1 会把「停用但无理由」判 FAIL；历史 16 条属此类。
    回填的是**理由**，不是把闸关掉 —— 理由内容全部来自
    `~/wiki/discussions/2026-09-19-Mimir-自查-剩余项核实与瑕疵清单.md` §2 的逐 job 评估
    （每条都有盘上判据）。本脚本把「理由表」变成可复算的代码，而不是手改 JSON。

安全约束（写生产 jobs.json ⇒ 保守）：
    * 默认 **dry-run**，只打印将要写入的改动；`--apply` 才写。
    * 写前备份 `jobs.json.bak-<UTC ts>-b1backfill`，写后**立即重读**并逐条断言；
    * 只增/改 `disable_reason` / `local_deliver_reason` 两个键，**不碰** enabled / next_run_at
      / deliver（改投递面是独立的、要单独验证的动作）；
    * 幂等：已有非空理由的 job 不覆盖（除非 `--force`），重复跑结果不变。

用法：
    python3 scripts/cron_backfill_disable_reasons.py            # dry-run
    python3 scripts/cron_backfill_disable_reasons.py --apply    # 落盘
    python3 scripts/cron_backfill_disable_reasons.py --jobs-file P --apply   # 测试用
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXIT_OK = 0
EXIT_FAIL = 1

# ---------------------------------------------------------------------------
# 理由表：job id 前 12 位 -> (键名, 理由文本)
# disable_reason = 已停用的理由；local_deliver_reason = 启用中但刻意为 local 的豁免说明。
# 来源：2026-09-19 自查卡 §2（B2 逐 job 影响评估）+ §1.1（B1 分母澄清）。
# ---------------------------------------------------------------------------
REASONS: Dict[str, Tuple[str, str]] = {
    "2a6a7d276c7f": (
        "disable_reason",
        "内容型（非监控）：纯增量信息采集，跑起来也不拦任何异常；wiki/log.md 09-13 起仍有人工入库通道 "
        "⇒ 恢复边际收益低。09-19 刘哥批：理由先记账，改造（deliver 改 feishu）后再议恢复。",
    ),
    "251d540c90e5": (
        "disable_reason",
        "内容型：每日会话蒸馏入库。09-18 起哑。恢复前置 = ①验证 dream_memory_cron.sh 在现记忆布局"
        "（MEMORY.md 60.7% / 双写 persistent.json）下可跑；②deliver 由 local 改 feishu。09-19 刘哥批：改造后恢复。",
    ),
    "9b707c3efbf9": (
        "disable_reason",
        "正式废弃（09-19 刘哥批）：数据源已死 —— data/reminders.json 停 06-27、data/stock_portfolio.json 停 06-24 "
        "⇒ 恢复 = 空转。保留记录不删。",
    ),
    "5c81beca2228": (
        "disable_reason",
        "真监控 · 待恢复（09-19 刘哥批）：本会拦下 wiki 重复页 / broken wikilinks / 成熟度晋级异常。"
        "09-19 已修日志落点（/tmp 会被清理 → ~/.mimiraether/logs）；剩余前置 = deliver 由 local 改 feishu。",
    ),
    "1b02c15ed283": (
        "disable_reason",
        "双重哑（门禁哑 + 数据源 data/verify-gate.log 停 08-18 14:53）。09-19 刘哥批：不原样恢复"
        "（5min × deliver=local = 永远后台死），与 Tier-0 nightly 失败告警合并重建。",
    ),
    "10517dc46dc7": (
        "disable_reason",
        "真监控 · 待恢复（09-19 刘哥批）：本会拦下「讨论室 status: mimir 卡无人处理」（接力棒掉落）。"
        "前置 = ①与 Buzz 收件箱自动唤醒判重（防 U11 双唤醒复发）；②deliver 改 feishu。",
    ),
    "1bc613c4aa65": (
        "disable_reason",
        "真监控 · 待恢复（09-19 刘哥批）：本会拦下语义索引静默退化（条数骤降/垃圾回流）。"
        "前置 = ①先做一次手工体检（已 30 天未体检）；②deliver 改 feishu。",
    ),
    "6851eebf830c": (
        "disable_reason",
        "真监控 · 待恢复（09-19 刘哥批）：本会拦下性能回归（延迟 P50/P95/P99 漂移）。只读、成本低；"
        "前置 = deliver 改 feishu。",
    ),
    "8e0995edbfb4": ("disable_reason", "一次性验收任务已完成（batch2 B4-b 窗口验收），保留为证据记录。"),
    "6b93ec1d048d": ("disable_reason", "一次性验收任务已完成（batch2 B4-b 窗口验收 v2），保留为证据记录。"),
    "17421ec5d44b": ("disable_reason", "一次性交棒任务已完成（dplan B4-b 验收 → batch3），保留为证据记录。"),
    "2b3d22f46c22": ("disable_reason", "一次性取证投递已完成（N5 重启窗口，末次 09-17 19:59）。"),
    "8b2a3379eb30": ("disable_reason", "一次性报告投递已完成（N9 生产验证），保留为证据记录。"),
    "5d64992d3fd4": ("disable_reason", "一次性报告投递已完成（N10 生产验证），保留为证据记录。"),
    "b95265ac9421": ("disable_reason", "一次性报告投递已完成（N13 生产正控），保留为证据记录。"),
    "6d82dd753060": (
        "local_deliver_reason",
        "设计如此：机械检查 runner 每小时跑，产出落 cron/output 与 logs；逐时投递会把飞书噪声化。"
        "失败可听性由 runner 退出码 + 台账承载 —— 无外部告警属已知缺口，随 verify-gate 合并重建一并处理。",
    ),
}


def _load(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        raise SystemExit(f"unexpected jobs.json shape: {type(jobs)}")
    return jobs


def plan(jobs: List[Dict[str, Any]], force: bool = False) -> List[Tuple[str, str, str]]:
    """返回 [(job_id12, key, action)]；action 属于 {set, skip_has_reason, skip_unknown_id}。"""
    out: List[Tuple[str, str, str]] = []
    for job in jobs:
        key12 = str(job.get("id") or "")[:12]
        if key12 not in REASONS:
            if not job.get("enabled"):
                out.append((key12, "-", "skip_unknown_id"))
            continue
        key, _text = REASONS[key12]
        if str(job.get(key) or "").strip() and not force:
            out.append((key12, key, "skip_has_reason"))
        else:
            out.append((key12, key, "set"))
    return out


def apply_plan(jobs: List[Dict[str, Any]], force: bool = False) -> List[Tuple[str, str]]:
    changed: List[Tuple[str, str]] = []
    for job in jobs:
        key12 = str(job.get("id") or "")[:12]
        if key12 not in REASONS:
            continue
        key, text = REASONS[key12]
        if str(job.get(key) or "").strip() and not force:
            continue
        job[key] = text
        changed.append((key12, key))
    return changed


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="B1 记账回填（默认 dry-run）")
    ap.add_argument("--jobs-file", default=str(Path.home() / ".mimiraether" / "cron" / "jobs.json"))
    ap.add_argument("--apply", action="store_true", help="真正写盘（默认只打印）")
    ap.add_argument("--force", action="store_true", help="覆盖已有理由（默认跳过）")
    args = ap.parse_args(argv)

    path = Path(args.jobs_file)
    if not path.exists():
        print(f"[backfill] SKIP: no jobs file at {path}")
        return EXIT_OK
    jobs = _load(path)
    actions = plan(jobs, force=args.force)
    for jid, key, act in actions:
        print(f"[backfill] {act:18s} {jid} {key}")
    to_set = [a for a in actions if a[2] == "set"]
    unknown = [a for a in actions if a[2] == "skip_unknown_id"]
    already = len(actions) - len(to_set) - len(unknown)
    print(f"[backfill] jobs={len(jobs)} to_set={len(to_set)} already={already} unknown_disabled={len(unknown)}")

    if not args.apply:
        print("[backfill] DRY-RUN（未写盘；加 --apply 生效）")
        return EXIT_OK

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + f".bak-{ts}-b1backfill")
    shutil.copy2(path, backup)
    changed = apply_plan(jobs, force=args.force)
    payload = {"jobs": jobs, "updated_at": datetime.now(timezone.utc).isoformat()}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

    reread = _load(path)
    missing = [
        str(j.get("id"))[:12]
        for j in reread
        if str(j.get("id"))[:12] in REASONS
        and not str(j.get(REASONS[str(j.get("id"))[:12]][0]) or "").strip()
    ]
    print(f"[backfill] wrote {len(changed)} entries; backup={backup.name}; reread_missing={missing}")
    return EXIT_FAIL if missing else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
