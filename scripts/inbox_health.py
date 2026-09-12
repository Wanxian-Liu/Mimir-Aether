#!/usr/bin/env python3
"""inbox_health.py — 四方收件箱新鲜度巡检（D8 / S5，2026-09-12 刘哥批）

目的（D5/D8 裁决）：「送达可验证」= 会议室签到簿。治「污染/丢包 3.5 个月无人发现」
的同型风险。**独立脚本起步**（D8 裁决：/health 噪声未清前不并入）。

每箱检查五项（只读，不改任何文件）：
  1. mtime 年龄        —— 多久没人写（新鲜度）
  2. 行数 vs offset    —— 不一致 = 有未消费积压（D2 契约）
  3. offset 文件存在   —— 无 offset = 该成员送达不可验证
  4. 契约键合规        —— 逐行 json.loads（try/except，容忍残行）+ content 键在位
                          （U2：subject/body = 违规；实测 hermes 箱曾有 17 行残行 + 3 条坏键）
  5. 最后写入者        —— 末行 from（谁的箱被谁单向刷屏）

退出码：0 = 全绿；1 = 有告警（--strict 时非绿即 1）。

用法：python3 inbox_health.py [--json] [--hours 24] [--members hermes,mimir]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

CANONICAL_DIR = Path(os.environ.get("BUZZ_INBOX_DIR", "/home/rayliu/.openclaw/data"))
MEMBERS = ("hermes", "openclaw", "loki", "mimir")
# U2 契约：载荷键必须是 content
VIOLATION_KEYS = ("subject", "body")


def _member_path(member: str) -> Path:
    return CANONICAL_DIR / f"buzz-inbox-{member}.jsonl"


def check_member(member: str, stale_hours: float) -> dict:
    path = _member_path(member)
    offset_path = path.with_suffix(".offset")
    info: dict = {"member": member, "path": str(path), "warnings": []}

    if not path.exists():
        info.update({"exists": False, "lines": 0, "offset": None, "debt": None,
                     "age_hours": None, "violations": 0, "residual": 0, "last_from": None})
        info["warnings"].append("收件箱不存在（该箱从未收到过消息）")
        return info

    stat = path.stat()
    age_hours = (time.time() - stat.st_mtime) / 3600.0
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    total = 0
    violations = 0
    residual = 0
    last_from = None
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            residual += 1          # 非 JSON 残行（实测 hermes 箱曾有 17 行）
            continue
        total += 1
        if isinstance(obj, dict):
            if "content" not in obj or not str(obj.get("content") or "").strip():
                violations += 1    # 坏键 / 空载荷 = 消费端读出空消息
            last_from = obj.get("from", last_from)

    offset = None
    if offset_path.exists():
        try:
            offset = int(offset_path.read_text().strip() or 0)
        except ValueError:
            offset = None
            info["warnings"].append("offset 文件内容非整数")
    else:
        info["warnings"].append("无 .offset —— 送达不可验证（D2 契约未满足）")

    debt = None if offset is None else len(raw_lines) - offset
    if debt is not None and debt > 0:
        info["warnings"].append(f"有 {debt} 行未消费积压（行数 {len(raw_lines)} > offset {offset}）")
    if age_hours > stale_hours:
        info["warnings"].append(f"箱 {age_hours:.1f}h 未更新（> 阈值 {stale_hours}h）")
    if violations:
        info["warnings"].append(f"{violations} 行缺 content 键或载荷为空（U2 契约违规）")
    if residual:
        info["warnings"].append(f"{residual} 行非 JSON 残行（读取端必须逐行 try/except）")

    info.update({"exists": True, "lines": len(raw_lines), "json_lines": total,
                 "offset": offset, "debt": debt, "age_hours": round(age_hours, 2),
                 "violations": violations, "residual": residual, "last_from": last_from,
                 "size": stat.st_size})
    return info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="四方收件箱新鲜度巡检（D8/S5）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--hours", type=float, default=24.0, help="新鲜度阈值（小时）")
    ap.add_argument("--members", default=",".join(MEMBERS))
    ap.add_argument("--strict", action="store_true", help="任一项告警即退出码 1")
    args = ap.parse_args(argv)

    members = [m.strip() for m in args.members.split(",") if m.strip()]
    results = [check_member(m, args.hours) for m in members]

    if args.json:
        print(json.dumps({"generated_at": int(time.time()), "canonical": str(CANONICAL_DIR),
                          "boxes": results}, ensure_ascii=False, indent=2))
    else:
        print(f"canonical={CANONICAL_DIR}  (阈值 {args.hours}h)")
        for r in results:
            flag = "OK " if not r["warnings"] else "WARN"
            debt = "-" if r["debt"] is None else r["debt"]
            print(f"[{flag}] {r['member']:<9} mtime={r['age_hours']}h lines={r['lines']} "
                  f"offset={r['offset']} debt={debt} badkey={r['violations']} residual={r['residual']} "
                  f"last_from={r['last_from']}")
            for w in r["warnings"]:
                print(f"        · {w}")
    return 1 if (args.strict and any(r["warnings"] for r in results)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
