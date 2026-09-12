#!/usr/bin/env python3
"""buzz_send.py — 四方信箱【发件端单点】（U4 / D7，2026-09-12 刘哥批）

背景（盘上事实）：
  `~/.mimiraether/scripts/` 下曾有 9 个一次性发件脚本各自硬编码收件人路径
  （其中 2 个仍指向已停更的 `~/.buzz-nostr/state/`），四方审计定位为
  「schema 漂移 + 路径漂移」的土壤（`hermes-comm-plan-1789216277` / D7 立项）。

契约（四方通信统一方案 U1/U2 · D1/D2）：
  - canonical 目录：`~/.openclaw/data/`（env `BUZZ_INBOX_DIR` 可覆盖）
  - 收件箱文件：`buzz-inbox-<to>.jsonl`（env `BUZZ_INBOX_<TO>` 可覆盖整路径）
  - 信封键：id / from / to / ts / kind / content（+ 可选 card / asks）
    · 载荷键**必须**是 `content`——历史上误用 `subject`/`body` 导致消费端读出空消息
  - kind 枚举：1 任务令 / 2 回执 / 3 审计票 / 4 待授权 / 5 状态查 / 9 到达信号

用法（代码）：
    from buzz_send import send
    send("hermes", "正文", kind=2, card="wiki/discussions/xxx.md", asks="请落段")

用法（命令）：
    python3 buzz_send.py --to hermes --kind 2 --content "..." [--card P] [--asks A] [--dry-run]
    echo "正文" | python3 buzz_send.py --to hermes --stdin
    python3 buzz_send.py --check --to hermes     # 只打印解析出的落点，不写

边界：纯新增，不替换任何既有脚本（既有脚本保持原样，逐一迁移）。回滚 = 删除本文件。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

CANONICAL_DIR = Path(os.environ.get("BUZZ_INBOX_DIR", "/home/rayliu/.openclaw/data"))
DEFAULT_SENDER = os.environ.get("BUZZ_SENDER", "mimir")
KIND_ENUM = {1: "任务令", 2: "回执", 3: "审计票", 4: "待授权", 5: "状态查", 9: "到达信号"}
# 历史漂移键：出现即视为违规（U2 信封契约）
FORBIDDEN_PAYLOAD_KEYS = ("subject", "body", "text", "message")


def resolve_inbox(to: str) -> Path:
    """收件箱落点：env `BUZZ_INBOX_<TO大写>` > canonical 目录。"""
    key = "BUZZ_INBOX_" + to.upper().replace("-", "_")
    override = os.environ.get(key) or os.environ.get("BUZZ_INBOX_" + to.upper())
    if override:
        return Path(override)
    return CANONICAL_DIR / f"buzz-inbox-{to}.jsonl"


def build_envelope(to: str, content: str, kind: int = 1, card: str | None = None,
                   asks: str | None = None, sender: str = DEFAULT_SENDER) -> dict:
    """构造标准信封（U2）。content 为空 = 违规，直接拒绝。"""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content 不能为空——空正文在消费端等于『没收到』")
    if kind not in KIND_ENUM:
        raise ValueError(f"kind 必须属于 {sorted(KIND_ENUM)}（U2 枚举）")
    envelope = {
        "id": f"{sender}-{int(time.time())}-{uuid.uuid4().hex[:6]}",
        "ts": int(time.time()),
        "from": sender,
        "to": to,
        "kind": kind,
        "content": content,
    }
    if card:
        envelope["card"] = card
    if asks:
        envelope["asks"] = asks
    return envelope


def send(to: str, content: str, kind: int = 1, card: str | None = None,
         asks: str | None = None, sender: str = DEFAULT_SENDER,
         dry_run: bool = False) -> dict:
    """唯一发件入口。返回信封 dict（dry_run 时不落盘）。"""
    env = build_envelope(to, content, kind=kind, card=card, asks=asks, sender=sender)
    path = resolve_inbox(to)
    if dry_run:
        return {"envelope": env, "path": str(path), "written": False}
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(env, ensure_ascii=False)
    # 单次 write + 换行：POSIX 下 O_APPEND 追加写，不整文件重写（并发安全）
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return {"envelope": env, "path": str(path), "written": True,
            "lines": sum(1 for _ in open(path, encoding="utf-8"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="四方信箱发件端单点（U4/D7）")
    ap.add_argument("--to", required=True, help="收件人：hermes / openclaw / loki / mimir")
    ap.add_argument("--content", default=None, help="正文（载荷键必须是 content）")
    ap.add_argument("--stdin", action="store_true", help="从 stdin 读正文")
    ap.add_argument("--kind", type=int, default=1, help="1任务令/2回执/3审计票/4待授权/5状态查/9到达")
    ap.add_argument("--card", default=None, help="关联讨论卡路径（U5 卡信伴生）")
    ap.add_argument("--asks", default=None, help="要求对方做什么（U5）")
    ap.add_argument("--from", dest="sender", default=DEFAULT_SENDER)
    ap.add_argument("--dry-run", action="store_true", help="只构造不落盘")
    ap.add_argument("--check", action="store_true", help="打印解析落点后退出")
    args = ap.parse_args(argv)

    path = resolve_inbox(args.to)
    if args.check:
        print(f"to={args.to} path={path} exists={path.exists()} "
              f"lines={sum(1 for _ in open(path, encoding='utf-8')) if path.exists() else 0}")
        return 0

    content = sys.stdin.read() if args.stdin else args.content
    if content is None:
        ap.error("需要 --content 或 --stdin")
    try:
        res = send(args.to, content, kind=args.kind, card=args.card,
                   asks=args.asks, sender=args.sender, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    verb = "DRY-RUN" if args.dry_run else "SENT"
    print(f"{verb} to={args.to} kind={args.kind}({KIND_ENUM[args.kind]}) id={res['envelope']['id']} "
          f"path={res['path']}" + (f" total_lines={res.get('lines')}" if res.get("written") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
