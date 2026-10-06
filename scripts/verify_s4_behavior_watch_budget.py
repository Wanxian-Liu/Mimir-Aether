#!/usr/bin/env python3
"""④ 判据脚本（S4 · 2026-10-06）：行为观察周报 job 的「额度上限」是否真在盘上生效。

用途 = §8.5「blocking 必配可跑判据」：一行可复制、rc 语义明确（0 过 / 1 拦）。

三查：
  R1 盘上 prompt 以 [tier:短] 开头（声明是**机制**入口，不是提示语）
  R2 分档机制把该 prompt 解析成 20 轮（复用 agent/max_turns_tier，不新建预算系统）
  R3 prompt 含预算三条（轮次硬顶 / 只读合并 1 次 / 止步落半段）
      —— 防止「声明在、规则被删」的漂移

用法（必须带仓内 venv —— 2026-10-06 复核 #2：裸 `python3` 会
`ModuleNotFoundError: No module named aiohttp`，因为 agent.max_turns_tier 的导入链
需要仓内依赖。契约要求「复核方原样粘贴即得读数」，故命令写全路径）：

    ~/src/MimirAether/.venv/bin/python3 scripts/verify_s4_behavior_watch_budget.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

JOB_ID = "a5d857fe4b09"
JOB_NAME = "mimir-behavior-watch-weekly"


def _home() -> Path:
    return Path(os.environ.get("MIMIR_AETHER_HOME") or Path.home() / ".mimiraether")


def main() -> int:
    jobs_path = _home() / "cron" / "jobs.json"
    data = json.loads(jobs_path.read_text(encoding="utf-8"))
    jobs = data["jobs"] if isinstance(data, dict) else data
    job = next((j for j in jobs if j.get("id") == JOB_ID), None)
    if job is None:
        print(f"R1 FAIL: jobs.json 里找不到 {JOB_ID}")
        return 1

    prompt = str(job.get("prompt") or "")
    failures = []

    r1 = prompt.startswith("[tier:短]")
    print(f"R1 [tier:短] 开头: {r1}")
    if not r1:
        failures.append("R1")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.max_turns_tier import resolve_max_turns_tier

    turns, tier, _cleaned = resolve_max_turns_tier(prompt, default=90)
    r2 = turns == 20 and tier == "short"
    print(f"R2 分档解析: turns={turns} tier={tier} ⇒ {r2}")
    if not r2:
        failures.append("R2")

    checks = {
        "轮次硬顶": "轮次硬顶 = 20 轮" in prompt,
        "只读合并": "合并成 1 次" in prompt,
        "止步落半段": "禁空手而回" in prompt,
    }
    r3 = all(checks.values())
    print(f"R3 预算三条: {checks} ⇒ {r3}")
    if not r3:
        failures.append("R3")

    print(f"job={JOB_NAME} id={JOB_ID} enabled={job.get('enabled')} deliver={job.get('deliver')!r}")
    if failures:
        print("VERDICT: FAIL " + ",".join(failures))
        return 1
    print("VERDICT: PASS (R1/R2/R3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
