#!/usr/bin/env python3
"""wiki-watcher 预扫描 + 唤醒（B2 #1 判重方案 · 2026-09-19 · 刘哥批）。

## 为什么存在（两个洞，一起堵）

洞 1 —— token 洞：cron job `mimir-wiki-watcher` 原是 `script: None` + prompt 形态
  ⇒ 无论有没有 `status: mimir` 的卡，每 5 分钟都起一次完整 LLM run（288 run/日）。
  `gateway/cron_mixin.py:945` 的 `[SILENT]` 只免投递、不免 token。
  ⇒ 本脚本走 cron script 模式（`cron_mixin.py:806-898`：有 script 则不起 agent），
    零 LLM 预扫描；有活时才 POST /v1/runs 唤醒（与 `buzz-inbox-watcher.sh` 同构）。

洞 2 —— 双唤醒洞（本方案主交付）：同一张卡可能被两个生产者唤醒
  （A：Buzz 收件箱 watcher；B：本 cron）。`gateway/wake_gate.py:108` 的
  `WAKE_TRIGGER_SOURCES` 不含裸 `api`，且 `/v1/runs` 的 `session_key` = 该 run
  自己的 trace_id ⇒ 单飞闸对这类唤醒结构性无效（INC-12 实测）。去重必须前置到派发前。

## 判重三层（全部前置在派发前）

L1 跨生产者抑制：收件箱有**新鲜未处理**行（A 的唤醒即将/正在发生）⇒ 本轮不唤醒。
   老化阈值 = SUPPRESS_WINDOW_S（默认 900s，对齐 wake_gate 的 15 分钟重复窗）。
   只在「新鲜」时抑制 ⇒ A 通路坏掉时未处理行会变旧，B 自动接管 = **fail-open**
   （安全网不因 A 死掉而失效；这是刻意的，不是遗漏）。
L2 逐卡认领：claims/<sha1(path)>.json 记 {path, content_hash, ts}；同哈希且未过
   CLAIM_TTL_S（默认 1800s）⇒ 跳过。防的是**唤醒到落段之间**的在飞窗口（慢 run 场景）。
L3 产品级幂等（沿用既有 BURNFIX）：卡里已有 ^## Mimir 段 ⇒ 已处理过，跳过。

## 输出契约（供 cron script 模式消费）

- 无事可做 / 被抑制 → **零输出**（cron 侧 `if not final_text.strip(): return` ⇒ 不投递、不噪声）
- 有活并成功唤醒 → 一行摘要（含卡名、数量）
- POST 失败 / 网关不可达 → stdout 带原因 + 退出码≠0（cron 记 error ⇒ 被投递 ⇒ 失败可听）

用法：
    python3 scripts/wiki_wake_scan.py                 # 生产
    python3 scripts/wiki_wake_scan.py --dry-run       # 只看判据，不 POST、不写认领
    python3 scripts/wiki_wake_scan.py --explain       # 打印每张卡的判定理由
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 路径与阈值：全部可 env 覆写 —— 可测性的前提（被测件必须能把真实对象重定向到夹具，
# 否则「测试」只能碰生产件）。默认值即生产值。
# ---------------------------------------------------------------------------
SUPPRESS_WINDOW_S = int(os.environ.get("WIKI_WAKE_SUPPRESS_WINDOW_S", "900"))
CLAIM_TTL_S = int(os.environ.get("WIKI_WAKE_CLAIM_TTL_S", "1800"))
CARD_STATUS_LINE = "status: mimir"
MIMIR_SECTION_PREFIX = "## Mimir"


def wiki_dir() -> Path:
    return Path(os.environ.get("WIKI_WAKE_WIKI_DIR", str(Path.home() / "wiki" / "discussions")))


def inbox_path() -> Path:
    return Path(
        os.environ.get(
            "WIKI_WAKE_INBOX",
            str(Path.home() / ".openclaw" / "data" / "buzz-inbox-mimir.jsonl"),
        )
    )


def offset_hint_path() -> Path:
    """**已退役**的旧水位文件路径（2026-10-07 退役 · 只读展示，禁作判据）。

    历史：旧收信循环把「读到第几行」写进 `<inbox>.offset`，其包装器
    `~/.hermes/scripts/buzz-mimir-auto.sh` 已改名留档 `.retired-20261007`，
    两个 cron 库零引用 ⇒ 该文件**不再被任何进程推进**，冻结在退役时刻的行号
    （实测冻结在 54，而信已全处理完 ⇒ 曾造成**永久假红**）。
    保留用途：历史诊断字段显示。禁删/改名（历史数据）。
    """
    return Path(os.environ.get("WIKI_WAKE_OFFSET", str(sidecar(".offset"))))


def sidecar(ext: str) -> Path:
    """收件箱旁挂文件的**生产命名**：`buzz-inbox-mimir.jsonl` → `buzz-inbox-mimir{ext}`。

    实测坑（本轮发现）：旧代码用 `str(inbox) + ".offset"` 拼出
    `buzz-inbox-mimir.jsonl.offset`，而生产侧旁挂文件**没有 .jsonl 段**
    （真名 `buzz-inbox-mimir.offset` / `.dispatched`）⇒ 旧默认路径恒指不存在的文件。
    """
    base = inbox_path()
    stem = base.name[: -len(".jsonl")] if base.name.endswith(".jsonl") else base.name
    return base.with_name(stem + ext)


def dispatched_path() -> Path:
    """活水位①：派发水位（watcher 侧维护）。env 覆写 `WIKI_WAKE_DISPATCHED`。"""
    return Path(os.environ.get("WIKI_WAKE_DISPATCHED", str(sidecar(".dispatched"))))


def ledger_path() -> Path:
    """活水位②：补账台账 `inbox-processed.log`（末条 `up to N` = 已消费水位）。

    env 覆写 `WIKI_WAKE_LEDGER`。默认路径 **HOME 无关**解析（沙箱 HOME 差异会拼出
    假路径 ⇒ 误报「量具不可用」，同 `check_inbox_ledger_lag.py` 2026-10-06 修）。
    """
    env_ledger = os.environ.get("WIKI_WAKE_LEDGER")
    if env_ledger:
        return Path(env_ledger)
    cands: List[Path] = []
    for k in ("MIMIR_AETHER_HOME", "MIMIR_HOME"):
        v = os.environ.get(k)
        if v:
            cands.append(Path(v) / "logs" / "inbox-processed.log")
    cands.append(Path.home() / ".mimiraether" / "logs" / "inbox-processed.log")
    cands.append(Path("/home/rayliu/.mimiraether/logs/inbox-processed.log"))
    for c in cands:
        if c.exists():
            return c
    return cands[-1]


# 台账水位行 = `processed N lines (up to M)`，M 即水位。锚定整句而非裸 `up to (\d+)`：
# 实测备注里出现过别的 `up to N` 数字（裸 regex 取 max 得 234 ≠ 末条 58）⇒ 必须锚句式
# 并取**最后一个**匹配（台账 append-only ⇒ 末条即当前水位）。
LEDGER_WM_RE = re.compile(r"processed\s+\d+\s+lines\s*\(up to\s+(\d+)\)")


def claim_dir() -> Path:
    return Path(
        os.environ.get(
            "WIKI_WAKE_CLAIM_DIR",
            str(Path.home() / ".mimiraether" / "data" / "wiki-waker" / "claims"),
        )
    )


def gateway_url() -> str:
    return os.environ.get("WIKI_WAKE_GATEWAY", "http://127.0.0.1:18999").rstrip("/")


def now_ts() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# 纯函数层（可单测，不碰盘）
# ---------------------------------------------------------------------------

def card_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def is_candidate(text: str) -> Tuple[bool, str]:
    """是否为待接棒候选卡。返回 (是否候选, 理由)。"""
    lines = text.splitlines()
    status_hit = any(l.strip() == CARD_STATUS_LINE for l in lines[:40])
    if not status_hit:
        return False, "status-not-mimir"
    if any(l.strip().startswith(MIMIR_SECTION_PREFIX) for l in lines):
        return False, "already-has-mimir-section(L3)"
    return True, "candidate"


def _read_int(path: "Path") -> Tuple[Optional[int], str]:
    """读整型水位文件。返回 (值 或 None, 状态)。

    状态语义：missing（文件不存在）/ unreadable（IO 或非整数）/ ok。
    **不把缺失读成 0** —— 0 是合法水位（第 0 行），缺失是「量具不可用」，两者必须可区分
    （否则负控与"真无积压"混为一谈）。
    """
    if not path.exists():
        return None, "missing"
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0"), "ok"
    except (ValueError, OSError):
        return None, "unreadable"


def read_ledger_watermark(path: "Path") -> Tuple[Optional[int], int, str]:
    """台账活水位 = **末条** `processed N lines (up to M)` 的 M。返回 (水位, 条目数, 状态)。"""
    if not path.exists():
        return None, 0, "missing"
    last: Optional[int] = None
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


def consumed_watermark(
    ledger: "Path", dispatched: "Path", offset_hint: Optional["Path"] = None
) -> Tuple[int, Dict[str, Any]]:
    """**消费水位**（P-2b · 2026-10-07）静水位 → 活水位。

    口径 = `max(台账末条 up to N, 收件箱 .dispatched)` —— 三源任一推进即视为该行已消费。

    为什么改：旧口径只认 `.offset`，而它随包装器退役后**冻结**（不再被推进）⇒
    已消费的行被永久读成未消费 = 永久假红（实测冻结 54 vs 全处理完）。
    为什么取 max 而不是取某一个：两个活水位维护者（watcher 派发 / 补账台账）节奏不同，
    任一领先都证明该行已被接手 ⇒ 取 max 才是「已消费」的正确下界。
    `.offset` 退役后**只作历史诊断字段显示**，不进 max（旧值即脏值：它偏小 ⇒ 会低估水位）。
    """
    led_wm, led_hits, led_state = read_ledger_watermark(ledger)
    dsp_wm, dsp_state = _read_int(dispatched)
    if led_wm is None and dsp_wm is None:
        # 两个活水位都不可用 ⇒ 保守：水位记 0（全部未消费 ⇒ 宁可抑制）。调用方按状态出理由。
        watermark, usable = 0, False
    else:
        watermark, usable = max(led_wm or 0, dsp_wm or 0), True
    meta: Dict[str, Any] = {
        "watermark": watermark,
        "usable": usable,
        "ledger_watermark": led_wm,
        "ledger_entries": led_hits,
        "ledger_state": led_state,
        "ledger_path": str(ledger),
        "dispatched_watermark": dsp_wm,
        "dispatched_state": dsp_state,
        "dispatched_path": str(dispatched),
        # 退役字段：只读展示，禁作判据（2026-10-07）
        "offset_hint_retired": None,
    }
    if offset_hint is not None:
        hint, _hint_state = _read_int(offset_hint)
        meta["offset_hint_retired"] = hint
        meta["offset_path_retired"] = str(offset_hint)
    return watermark, meta


def inbox_pending(
    inbox: "Path", offset: "Path", dispatched: Optional["Path"] = None, ledger: Optional["Path"] = None
) -> Tuple[int, Optional[float], str]:
    """返回 (未处理行数, 最新未处理行的 epoch ts 或 None, 理由)。

    未处理行数 = 总行数 - **消费水位**（活水位 max(台账, .dispatched)）。
    最新未处理行的 ts 取**该行自身**的 `ts` 字段；解析失败则返回 None
    （调用方退化为用文件 mtime 判新鲜度 —— 宁可抑制也不双唤醒）。

    兼容：`offset` 位置参数保留但已退役（只作 hint），活水位走
    `dispatched`/`ledger`（None ⇒ 用默认路径）。
    """
    if not inbox.exists():
        return 0, None, "inbox-missing"
    try:
        raw = inbox.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, None, "inbox-unreadable"
    blank = [k for k, l in enumerate(raw) if not l.strip()]
    if blank:
        del raw[blank[0]:]
    total = len(raw)
    wm, meta = consumed_watermark(
        ledger if ledger is not None else ledger_path(),
        dispatched if dispatched is not None else dispatched_path(),
        offset,
    )
    pending = max(0, total - wm)
    if pending == 0:
        return 0, None, "no-pending"
    # 只吃「最后 wm 行之后」的行 —— 前段行既无 ts 也无信息量
    tail = raw[wm:]
    last = None
    for line in reversed(tail):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            last = float(obj.get("ts")) if isinstance(obj, dict) and obj.get("ts") is not None else None
        except (ValueError, TypeError, json.JSONDecodeError):
            last = None
        break
    why = "pending" if meta["usable"] else "pending-watermark-unknown"
    return pending, last, why


def suppression_reason(inbox: "Path", offset: "Path", now: Optional[float] = None) -> Optional[str]:
    """L1 跨生产者抑制：A 通路有**新鲜**未处理行 ⇒ 返回抑制理由，否则 None。

    新鲜度 = 未处理行的 ts 年龄（取不到 ts 则退化为箱 mtime）。
    2026-10-07：未处理行的判定改用活水位（`.offset` 已退役）。
    """
    now = now if now is not None else now_ts()
    pending, last_ts, why = inbox_pending(inbox, offset)
    if pending <= 0:
        return None
    if last_ts is None:
        try:
            last_ts = inbox.stat().st_mtime
        except OSError:
            return f"inbox-pending({pending})-{why}-unknown-age->suppress"
    age = now - float(last_ts)
    if age <= SUPPRESS_WINDOW_S:
        return f"inbox-pending({pending})-{why}-fresh({int(age)}s<={SUPPRESS_WINDOW_S}s)->suppress"
    return None


def claim_path(path: "Path") -> "Path":
    return claim_dir() / (hashlib.sha1(str(path).encode()).hexdigest() + ".json")


def claim_state(path: "Path", text: str, now: Optional[float] = None) -> Tuple[bool, str]:
    """L2 逐卡认领：返回 (是否应跳过, 理由)。"""
    now = now if now is not None else now_ts()
    cp = claim_path(path)
    if not cp.exists():
        return False, "no-claim"
    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "claim-unreadable"
    if data.get("content_hash") != card_hash(text):
        return False, "claim-hash-changed"
    age = now - float(data.get("ts") or 0)
    if age <= CLAIM_TTL_S:
        return True, f"claim-fresh({int(age)}s<={CLAIM_TTL_S}s)"
    return False, f"claim-stale({int(age)}s)"


def write_claim(path: "Path", text: str) -> None:
    cp = claim_path(path)
    cp.parent.mkdir(parents=True, exist_ok=True)
    payload = {"path": str(path), "content_hash": card_hash(text), "ts": now_ts()}
    cp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def scan(explain: bool = False) -> Tuple[List["Path"], List[str]]:
    """返回 (待唤醒卡列表, 逐条理由行)。"""
    wd = wiki_dir()
    reasons: List[str] = []
    cands: List["Path"] = []
    if not wd.is_dir():
        return [], [f"wiki-dir-missing: {wd}"]
    for p in sorted(wd.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            reasons.append(f"{p.name}: unreadable ({exc})")
            continue
        ok, why = is_candidate(text)
        if not ok:
            if explain:
                reasons.append(f"{p.name}: skip [{why}]")
            continue
        skip, cwhy = claim_state(p, text)
        if skip:
            reasons.append(f"{p.name}: skip [L2 {cwhy}]")
            continue
        cands.append(p)
        if explain:
            reasons.append(f"{p.name}: WAKE [{cwhy}]")
    return cands, reasons


# ---------------------------------------------------------------------------
# 唤醒层
# ---------------------------------------------------------------------------

WAKE_TEMPLATE = (
    "【wiki-watcher 自动唤醒】讨论室有 {n} 张 status: mimir 的卡等你接棒：\n{cards}\n"
    "请逐张处理（读卡→盘上取证→在你的段里写结论→把 frontmatter 交棒给下一位）。"
    "卡目录：{wiki}\n"
    "纪律：只写自己的段、禁整卡覆盖；拍板类问题留给刘哥；"
    "处理完在 ~/.mimiraether/logs/wiki-waker.log 追加一行。"
)


def poke(cands: List["Path"], timeout: int = 10) -> Tuple[bool, str]:
    """POST /v1/runs 唤醒。返回 (是否成功, 详情)。"""
    body = json.dumps(
        {
            "input": WAKE_TEMPLATE.format(
                n=len(cands),
                cards="\n".join("- " + p.name for p in cands),
                wiki=str(wiki_dir()),
            ),
            "metadata": {"source": "wiki-watcher"},
        }
    )
    url = gateway_url() + "/v1/runs"
    try:
        proc = subprocess.run(
            ["curl", "-s", "-m", str(timeout), "-X", "POST", url,
             "-H", "Content-Type: application/json", "-d", body],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"curl-failed: {exc}"
    out = (proc.stdout or "") + (proc.stderr or "")
    if '"status"' in out and any(s in out for s in ('"started"', '"running"', '"completed"')):
        return True, out[:120]
    return False, f"gateway-rejected(rc={proc.returncode}): {out[:160]}"


def log_line(text: str) -> None:
    lp = Path(os.environ.get("WIKI_WAKE_LOG", str(Path.home() / ".mimiraether" / "logs" / "wiki-waker.log")))
    try:
        lp.parent.mkdir(parents=True, exist_ok=True)
        with open(lp, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat()} {text}\n")
    except OSError:
        pass  # 日志不可写不得影响唤醒判定


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="wiki-watcher 预扫描 + 唤醒（判重前置）")
    ap.add_argument("--dry-run", action="store_true", help="只判定，不 POST、不写认领")
    ap.add_argument("--explain", action="store_true", help="打印逐卡判定理由")
    args = ap.parse_args(argv)

    reason = suppression_reason(inbox_path(), offset_hint_path())
    if reason:
        log_line(f"SUPPRESS {reason}")
        if args.explain:
            print(f"[L1] {reason}")
        return 0  # 零输出：cron 侧不投递

    cands, reasons = scan(explain=args.explain)
    if args.explain:
        for r in reasons:
            print("[scan]", r)
    if not cands:
        log_line("IDLE no-candidate")
        return 0

    if args.dry_run:
        print(f"[dry-run] would wake for {len(cands)} card(s): " + ", ".join(p.name for p in cands))
        return 0

    ok, detail = poke(cands)
    if not ok:
        log_line(f"WAKE-FAIL n={len(cands)} {detail}")
        print(f"[wiki-wake] 唤醒失败: {detail}")
        return 1  # 非零 ⇒ cron 记 error ⇒ 投递 ⇒ 失败可听

    for p in cands:
        try:
            write_claim(p, p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    names = ", ".join(p.stem for p in cands)
    log_line(f"WAKE ok n={len(cands)} cards={names}")
    print(f"🎯 wiki-watcher: 已唤醒 {len(cands)} 张卡待接棒 — {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
