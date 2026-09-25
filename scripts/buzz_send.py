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
import re
import sys
import time
import uuid
from pathlib import Path
try:
    from report_template import raise_safe
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from report_template import raise_safe

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
DEFAULT_SENDER = os.environ.get("BUZZ_SENDER", "mimir")
KIND_ENUM = {1: "任务令", 2: "回执", 3: "审计票", 4: "待授权", 5: "状态查", 9: "到达信号"}
# 历史漂移键：出现即视为违规（U2 信封契约）
FORBIDDEN_PAYLOAD_KEYS = ("subject", "body", "text", "message")

# C 组 C4（2026-09-16）· 双重编码守卫。
# 历史事故：三箱各有 1 行 `card` 字段里存的是**字面** `\u56db\u65b9…`（已二次转义的 JSON 文本），
# 机器按字段取路径必然取不到；人读 content 正文却看不出问题（人工链路好、机器链路坏）。
# 判据：真中文路径**不可能**含字面 `\uXXXX` / `\/` 序列 ⇒ 出现即拒绝（fail loud，不静默写坏指针）。
_ESCAPE_MARKER_RE = re.compile(r"\\u[0-9a-fA-F]{4}|\\/")
CARD_ABS_PREFIXES = ("/", "~")


def validate_card(card):
    """校验机器可读指针 card。返回 (规范化值 | None, 告警列表)。违规抛 ValueError。"""
    if card is None:
        return None, []
    if not isinstance(card, str):
        raise_safe(ValueError, "card 必须是字符串，收到 %s", type(card).__name__)
    value = card.strip()
    if not value:
        raise ValueError("card 不能是空串——空指针在消费端等于『没给』")
    if _ESCAPE_MARKER_RE.search(value):
        raise ValueError(
            "card 疑似双重编码（含字面转义序列 \\uXXXX 或 \\/）：收方按字段取路径会取不到。"
            "请传纯路径字符串，序列化时用 json.dumps(..., ensure_ascii=False)"
        )
    warnings = []
    if value.startswith(CARD_ABS_PREFIXES):
        if not Path(os.path.expanduser(value)).exists():
            # 不阻断（卡可能尚未落盘、或已被归档——归档会移走路径），但必须留痕。
            warnings.append(f"card 指向的路径当前不存在：{value}")
    return value, warnings


def resolve_inbox(to: str) -> Path:
    """收件箱落点：env `BUZZ_INBOX_<TO大写>` > canonical 目录。"""
    key = "BUZZ_INBOX_" + to.upper().replace("-", "_")
    override = os.environ.get(key) or os.environ.get("BUZZ_INBOX_" + to.upper())
    if override:
        return Path(override)
    return CANONICAL_DIR / f"buzz-inbox-{to}.jsonl"


def build_envelope(to: str, content: str, kind: int = 1, card: str | None = None,
                   asks: str | None = None, sender: str = DEFAULT_SENDER,
                   warnings: list | None = None) -> dict:
    """构造标准信封（U2）。content 为空 = 违规，直接拒绝。"""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content 不能为空——空正文在消费端等于『没收到』")
    if kind not in KIND_ENUM:
        raise_safe(ValueError, "kind 必须属于 %s（U2 枚举）", sorted(KIND_ENUM))
    envelope = {
        "id": f"{sender}-{int(time.time())}-{uuid.uuid4().hex[:6]}",
        "ts": int(time.time()),
        "from": sender,
        "to": to,
        "kind": kind,
        "content": content,
    }
    if card:
        card_value, card_warnings = validate_card(card)
        if card_value:
            envelope["card"] = card_value
        if warnings is None:
            warnings = []
        warnings.extend(card_warnings)
    if asks:
        envelope["asks"] = asks
    return envelope


def send(to: str, content: str, kind: int = 1, card: str | None = None,
         asks: str | None = None, sender: str = DEFAULT_SENDER,
         dry_run: bool = False) -> dict:
    """唯一发件入口。返回信封 dict（dry_run 时不落盘）。落盘后做**回写校验**。"""
    warnings: list = []
    env = build_envelope(to, content, kind=kind, card=card, asks=asks,
                         sender=sender, warnings=warnings)
    path = resolve_inbox(to)
    if dry_run:
        return {"envelope": env, "path": str(path), "written": False, "warnings": warnings}
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(env, ensure_ascii=False)
    # 单次 write + 换行：POSIX 下 O_APPEND 追加写，不整文件重写（并发安全）
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    # C4 回写校验：末行必须可解析、且 id 与本次信封一致
    # （防截断 / 编码损坏 / 并发错行；不带此行则「写了」不等于「写对了」）
    with open(path, "rb") as fh:
        tail = fh.read().splitlines()[-1].decode("utf-8")
    try:
        written_env = json.loads(tail)
    except json.JSONDecodeError as exc:
        raise_safe(RuntimeError, "回写校验失败：末行不可解析（%s）path=%s", exc, path, cause=exc)
    if written_env.get("id") != env["id"]:
        raise RuntimeError(
            f"回写校验失败：末行 id={written_env.get('id')!r} != 本次 {env['id']!r} path={path}"
        )
    return {"envelope": env, "path": str(path), "written": True, "verified": True,
            "lines": sum(1 for _ in open(path, encoding="utf-8")), "warnings": warnings}


def append_envelope(to: str, envelope: dict) -> dict:
    """E7 低层追加入口：把**已构造好的**信封追加到收件箱单点，并做回写校验。

    与 send() 的分工：send() 负责「构造标准信封 + 落盘」；本函数只管「落哪 + 怎么落 + 落对没」，
    载荷（信封字段）由调用方给 ⇒ 历史脚本可**原样保留自己的信封形状**迁到单点，
    不必被强制重塑成 U2 契约（重塑会改载荷 = 改语义，不是迁移）。

    契约（与 send() 同一套）：仍强制 `content` 非空、`kind` 在枚举内。
    """
    if not isinstance(envelope, dict):
        raise_safe(ValueError, "envelope 必须是 dict，收到 %s", type(envelope).__name__)
    content = envelope.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content 不能为空——空正文在消费端等于『没收到』")
    kind = envelope.get("kind")
    if kind not in KIND_ENUM:
        raise_safe(ValueError, "kind 必须属于 %s（U2 枚举），收到 %r", sorted(KIND_ENUM), kind)
    env = dict(envelope)
    env.setdefault("to", to)
    env.setdefault("from", DEFAULT_SENDER)
    env.setdefault("ts", int(time.time()))
    env.setdefault("id", f"{env['from']}-{int(time.time())}-{uuid.uuid4().hex[:6]}")
    path = resolve_inbox(to)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(env, ensure_ascii=False) + "\n")
    with open(path, "rb") as fh:
        tail = fh.read().splitlines()[-1].decode("utf-8")
    try:
        written = json.loads(tail)
    except json.JSONDecodeError as exc:
        raise_safe(RuntimeError, "回写校验失败：末行不可解析（%s）path=%s", exc, path, cause=exc)
    if written.get("id") != env["id"]:
        raise RuntimeError(
            f"回写校验失败：末行 id={written.get('id')!r} != 本次 {env['id']!r} path={path}"
        )
    return {"envelope": env, "path": str(path), "written": True, "verified": True,
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
    for w in res.get("warnings") or []:
        print(f"WARN: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
