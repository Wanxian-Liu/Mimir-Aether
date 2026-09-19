#!/usr/bin/env python3
"""Cron 记账卫生闸（B1/B3 · 2026-09-19 · 刘哥批）。

为什么（根因，不是洁癖）：
    ~/.mimiraether/cron/jobs.json 长期存在三种「写而不跑 · 判据存在但没人读」的形态：
      ① enabled=false 而**没有任何理由字段** ⇒ 下一轮接手的人（含我）无法判断
         「这是刻意停的，还是坏了漏停的」——本轮自查实测 20/21 属此类。
      ② enabled=true 而 deliver 以 local 起 ⇒ 「跑起来了但没人收得到」，
         静默失败不可听（N8/N9/N10 同族病根）。
      ③ enabled=true 而 next_run_at 冻结在过去 ⇒ 调度器不会真跑它。
    三者都不是「能不能跑」的问题，而是**判据在盘上但没人读**。本闸把这三条变成机器
    判据，接进 Tier-0 Gate1（守卫式 if ! ...; then exit 1; fi，防 set +e 吞码）。

规则（只读状态；本脚本**从不写** jobs.json）：
    R1 FAIL  enabled=false 且 disable_reason/paused_reason 皆空
    R2 FAIL  enabled=true 且 deliver 以 local 起（豁免：local_deliver_reason 非空）
    R3 WARN  enabled=true 且 next_run_at 早于 now（冻结；WARN 不改变退出码）

退出码：0 = 无 FAIL（WARN 允许，照打）；1 = 至少一条 FAIL；jobs 文件不存在 = SKIP(0)
（CI 上没有 ~/.mimiraether ⇒ 必须 SKIP 而非红）。

负控（必带，见 --selftest 与 tests/scripts/test_check_cron_hygiene.py）：
    合成三病例分别断言 FAIL / FAIL / WARN，加**孪生合规对照**断言 PASS —— 只证明
    「坏样本被拒」不算数，必须同时证明「好样本不被误拦」。

用法：
    python3 scripts/check_cron_hygiene.py                 # 查真实 jobs.json
    python3 scripts/check_cron_hygiene.py --selftest      # 合成病例自证
    python3 scripts/check_cron_hygiene.py --jobs-file P   # 指定文件（测试用）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXIT_OK = 0
EXIT_FAIL = 1

RULE_DISABLED_NO_REASON = "R1"
RULE_ENABLED_LOCAL = "R2"
RULE_ENABLED_FROZEN = "R3"


def default_jobs_file() -> Path:
    home = os.environ.get("MIMIR_HOME")
    if not home:
        try:  # 与运行时同一真源；import 失败退回约定路径
            from mimir_constants import get_mimir_home  # type: ignore

            home = str(get_mimir_home())
        except Exception:
            home = str(Path.home() / ".mimiraether")
    return Path(home) / "cron" / "jobs.json"


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _reason_of(job: Dict[str, Any]) -> str:
    """停用理由：disable_reason 或 paused_reason 任一非空即算记账。"""
    for key in ("disable_reason", "paused_reason"):
        val = job.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def evaluate(
    jobs: List[Dict[str, Any]], now: Optional[datetime] = None
) -> List[Tuple[str, str, str]]:
    """返回 [(rule, level, message)]，level 属于 {FAIL, WARN}。"""
    now = now or datetime.now(timezone.utc)
    findings: List[Tuple[str, str, str]] = []
    for idx, job in enumerate(jobs):
        name = str(job.get("name") or job.get("id") or f"#{idx}")
        jid = str(job.get("id") or "")[:12]
        tag = f"{name} [{jid}]"
        if not job.get("enabled"):
            if not _reason_of(job):
                findings.append(
                    (
                        RULE_DISABLED_NO_REASON,
                        "FAIL",
                        f"{tag}: 已停用但无理由（disable_reason/paused_reason 皆空）",
                    )
                )
            continue
        deliver = str(job.get("deliver") or "")
        if deliver.startswith("local") and not str(
            job.get("local_deliver_reason") or ""
        ).strip():
            findings.append(
                (
                    RULE_ENABLED_LOCAL,
                    "FAIL",
                    f"{tag}: 启用中但 deliver={deliver}（启用即静默；需改 deliver 或给 local_deliver_reason）",
                )
            )
        nxt = _parse_ts(job.get("next_run_at"))
        if nxt is not None and nxt < now:
            findings.append(
                (
                    RULE_ENABLED_FROZEN,
                    "WARN",
                    f"{tag}: 启用中但 next_run_at={nxt.isoformat()} 已过（冻结）",
                )
            )
    return findings


def _load(path: Path) -> Optional[List[Dict[str, Any]]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[cron-hygiene] UNREADABLE {path}: {exc}")
        return None
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    return jobs if isinstance(jobs, list) else []


def run(path: Path) -> int:
    jobs = _load(path)
    if jobs is None:
        print(f"[cron-hygiene] SKIP (no jobs file at {path})")
        return EXIT_OK
    findings = evaluate(jobs)
    fails = [f for f in findings if f[1] == "FAIL"]
    warns = [f for f in findings if f[1] == "WARN"]
    for rule, level, msg in findings:
        print(f"[cron-hygiene] {level} {rule}: {msg}")
    print(
        f"[cron-hygiene] jobs={len(jobs)} fail={len(fails)} warn={len(warns)} file={path}"
    )
    if not findings:
        print("[cron-hygiene] OK: 记账面与投递面无一 FAIL/WARN")
    return EXIT_FAIL if fails else EXIT_OK


# ---------------------------------------------------------------------------
# 负控自证：三种坏病例 + 三条孪生合规对照
# ---------------------------------------------------------------------------


def _mk_job(jid: str, name: str, **over: Any) -> Dict[str, Any]:
    job: Dict[str, Any] = {
        "id": jid,
        "name": name,
        "enabled": True,
        "deliver": "feishu:oc_x",
        "next_run_at": "2999-01-01T00:00:00+00:00",
        "schedule": {"type": "cron", "value": "0 8 * * *"},
    }
    job.update(over)
    return job


def selftest() -> int:
    fixed_now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    cases = [
        ("bad_no_reason", _mk_job("b1", "坏-停用无理由", enabled=False), [RULE_DISABLED_NO_REASON]),
        ("bad_local", _mk_job("b2", "坏-启用但 local", deliver="local"), [RULE_ENABLED_LOCAL]),
        (
            "bad_frozen",
            _mk_job("b3", "坏-启用但冻结", next_run_at="2026-08-19T03:46:01+00:00"),
            [RULE_ENABLED_FROZEN],
        ),
        ("twin_ok_enabled", _mk_job("g1", "孪生-启用且 feishu"), []),
        (
            "twin_ok_disabled_reason",
            _mk_job("g2", "孪生-停用有理由", enabled=False, disable_reason="一次性任务已完成"),
            [],
        ),
        (
            "twin_ok_local_exempt",
            _mk_job("g3", "孪生-local 有豁免", deliver="local", local_deliver_reason="runner 只落台账"),
            [],
        ),
    ]
    ok = True
    for label, job, expect in cases:
        got = sorted({r for r, _lvl, _m in evaluate([job], now=fixed_now)})
        want = sorted(set(expect))
        good = got == want
        ok = ok and good
        level = "WARN" if want == [RULE_ENABLED_FROZEN] else ("FAIL" if want else "PASS")
        print(f"[selftest] {'PASS' if good else 'FAIL'} {label}: 期望 {level} {want or '-'} / 实得 {got or '-'}")
    print(f"[selftest] {'ALL PASS' if ok else 'HAS FAILURE'}")
    return EXIT_OK if ok else EXIT_FAIL


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Cron 记账卫生闸（只读）")
    ap.add_argument("--jobs-file", default=None, help="jobs.json 路径（默认 MIMIR_HOME/cron/jobs.json）")
    ap.add_argument("--selftest", action="store_true", help="跑合成负控/孪生对照")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(Path(args.jobs_file) if args.jobs_file else default_jobs_file())


if __name__ == "__main__":
    sys.exit(main())
