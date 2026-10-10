#!/usr/bin/env python3
"""inbox_health.py — 四方收件箱新鲜度巡检（D8 / S5，2026-09-12 刘哥批）

目的（D5/D8 裁决）：「送达可验证」= 会议室签到簿。治「污染/丢包 3.5 个月无人发现」
的同型风险。**独立脚本起步**（D8 裁决：/health 噪声未清前不并入）。

每箱检查五项（只读，不改任何文件）：
  1. mtime 年龄        —— 多久没人写（新鲜度）
  2. 行数 vs 消费水位  —— 行数 > 水位 = 有未消费积压（D2 契约 · 2026-10-07 改）
  3. 活水位可用（至少一源）—— 无活水位 = 该成员送达不可验证
  4. 契约键合规        —— 逐行 json.loads（try/except，容忍残行）+ content 键在位
                          （U2：subject/body = 违规；实测 hermes 箱曾有 17 行残行 + 3 条坏键）
  5. 最后写入者        —— 末行 from（谁的箱被谁单向刷屏）

## D2 契约 · 消费水位口径（2026-10-07 改 · 死水位退役）

**消费水位 = max( 台账 `inbox-processed.log` 末条 `up to N` , 收件箱 `.dispatched` )**
——三源任一推进即视为该行已消费。

**为什么改**：旧 D2 契约认 `<inbox>.offset`。该文件的唯一写者 `buzz-mimir-auto.sh`
已退役（改名 `.retired-20261007`）、cron 零引用 ⇒ `.offset` **不再被推进**，冻结在
退役时刻的行号 ⇒ 「无 offset ⇒ 送达不可验证」会把**已上线且完好**的箱读成不可验证
（实测 mimir 箱冻结 54 / 实收 61 行 ⇒ 永久假红）。

**`.offset` 保留为历史诊断字段**（可读不可作判据）：JSON 里 `offset`/`offset_hint`
仅展示，`watermark`/`debt` 一律由活水位算。

退出码：0 = 全绿；1 = 有告警（--strict 时非绿即 1）。

用法：python3 inbox_health.py [--json] [--hours 24] [--members hermes,mimir]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

def _os_home() -> Path:
    """OS 家目录。

    本机存在**双语义**：terminal/沙箱里 ``HOME`` 就是 mimir home
    （``/home/<user>/.mimiraether``），而 gateway 进程里 ``HOME`` 是 ``/home/<user>``。
    故先用单一真源 ``get_mimir_home()``，若其名恰为 ``.mimiraether`` 则上溯一层。
    """
    try:
        _root = Path(__file__).resolve().parents[1]
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from mimir_constants import get_mimir_home  # type: ignore

        h = get_mimir_home()
    except Exception:
        h = Path.home() / ".mimiraether"
    return h.parent if h.name == ".mimiraether" else Path.home()


def _default_canonical_dir() -> Path:
    """canonical 收件箱目录默认值（env ``BUZZ_INBOX_DIR`` 优先覆盖整路径）。"""
    return _os_home() / ".openclaw" / "data"


CANONICAL_DIR = Path(os.environ.get("BUZZ_INBOX_DIR", str(_default_canonical_dir())))
MEMBERS = ("hermes", "openclaw", "loki", "mimir")
# U2 契约：载荷键必须是 content
VIOLATION_KEYS = ("subject", "body")

# ---------------------------------------------------------------------------
# 消费水位（2026-10-07 · 死水位退役）—— 见模块 docstring「D2 契约 · 消费水位口径」
# ---------------------------------------------------------------------------
DEFAULT_LEDGER = os.environ.get(
    "MIMIR_LEDGER",
    str(Path.home() / ".mimiraether" / "logs" / "inbox-processed.log"),
)
# 锚定整句：台账备注里出现过别的 `up to N` 数字 ⇒ 裸 regex 会误取（实测 max 得 234 ≠ 末条 58）
LEDGER_WM_RE = re.compile(r"processed\s+\d+\s+lines\s*\(up to\s+(\d+)\)")


def _read_int(path: Path) -> tuple:
    """读整型水位文件 → (值 或 None, 状态)。**不把缺失读成 0**（0 是合法水位，缺失=量具不可用）。"""
    if not path.exists():
        return None, "missing"
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0"), "ok"
    except (ValueError, OSError):
        return None, "unreadable"


def read_ledger_watermark(path: Path) -> tuple:
    """台账活水位 = **末条** `processed N lines (up to M)` 的 M → (水位, 条目数, 状态)。"""
    if not path.exists():
        return None, 0, "missing"
    last = None
    hits = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = LEDGER_WM_RE.search(line)
                if m:
                    last = int(m.group(1))
                    hits += 1
    except OSError:
        return None, 0, "unreadable"
    return (last, hits, "ok") if last is not None else (None, 0, "no-watermark")


def consumed_watermark(inbox_path: Path) -> dict:
    """成员箱消费水位 = max(台账末条 up to N, `.dispatched`)。返回明细 dict（含退役字段）。"""
    ledger = Path(os.environ.get("MIMIR_LEDGER", DEFAULT_LEDGER))
    dsp_path = inbox_path.with_suffix(".dispatched")
    offset_path = inbox_path.with_suffix(".offset")     # 退役：只展示
    led_wm, led_hits, led_state = read_ledger_watermark(ledger)
    dsp_wm, dsp_state = _read_int(dsp_path)
    off_hint, off_state = _read_int(offset_path)
    usable = not (led_wm is None and dsp_wm is None)
    watermark = max(led_wm or 0, dsp_wm or 0) if usable else 0
    return {
        "watermark": watermark,
        "usable": usable,
        "ledger_watermark": led_wm,
        "ledger_state": led_state,
        "ledger_entries": led_hits,
        "ledger_path": str(ledger),
        "dispatched_watermark": dsp_wm,
        "dispatched_state": dsp_state,
        "dispatched_path": str(dsp_path),
        # 退役字段（2026-10-07）：只读展示，不参与任何判据
        "offset_hint_retired": off_hint,
        "offset_state_retired": off_state,
    }


def _member_path(member: str) -> Path:
    return CANONICAL_DIR / f"buzz-inbox-{member}.jsonl"


def check_member(member: str, stale_hours: float) -> dict:
    path = _member_path(member)
    offset_path = path.with_suffix(".offset")
    info: dict = {"member": member, "path": str(path), "warnings": []}

    if not path.exists():
        info.update({"exists": False, "lines": 0, "offset": None, "watermark": None,
                     "consumed": {"watermark": None, "usable": False},
                     "debt": None, "age_hours": None, "violations": 0, "residual": 0,
                     "last_from": None})
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

    # 消费水位（活口径）：max(台账末条 up to N, .dispatched)；`.offset` 退役只展示
    wm = consumed_watermark(path)
    if not wm["usable"]:
        info["warnings"].append(
            "无活水位（台账无 `up to N` 且无 .dispatched）—— 送达不可验证（D2 契约未满足）"
        )
    debt = None if not wm["usable"] else len(raw_lines) - wm["watermark"]
    if debt is not None and debt > 0:
        info["warnings"].append(
            f"有 {debt} 行未消费积压（行数 {len(raw_lines)} > 消费水位 {wm['watermark']}）"
        )
    if age_hours > stale_hours:
        info["warnings"].append(f"箱 {age_hours:.1f}h 未更新（> 阈值 {stale_hours}h）")
    if violations:
        info["warnings"].append(f"{violations} 行缺 content 键或载荷为空（U2 契约违规）")
    if residual:
        info["warnings"].append(f"{residual} 行非 JSON 残行（读取端必须逐行 try/except）")

    info.update({"exists": True, "lines": len(raw_lines), "json_lines": total,
                 "offset": wm["offset_hint_retired"],          # 退役字段：只展示
                 "watermark": wm["watermark"] if wm["usable"] else None,
                 "consumed": wm,
                 "debt": debt, "age_hours": round(age_hours, 2),
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
            wmv = "-" if r.get("watermark") is None else r["watermark"]
            print(f"[{flag}] {r['member']:<9} mtime={r['age_hours']}h lines={r['lines']} "
                  f"watermark={wmv} debt={debt} badkey={r['violations']} residual={r['residual']} "
                  f"last_from={r['last_from']} "
                  f"[退役·只读: offset={r['offset']}]")
            for w in r["warnings"]:
                print(f"        · {w}")
    return 1 if (args.strict and any(r["warnings"] for r in results)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
