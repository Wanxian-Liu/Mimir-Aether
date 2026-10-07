# -*- coding: utf-8 -*-
"""inbox_claim_gate.py — api 直连通道与 buzz-watcher 共用同一套收件箱认领闸（I-2 · 2026-10-07）

## 为什么两条通道必须共用一个 claim

派单方脚本 `~/.hermes/scripts/mimir-send.sh` 把**同一封信封**走两条路：
  ① 追加一行到 buzz 收件箱 `buzz-inbox-mimir.jsonl`（留档）
  ② 立刻 `POST /v1/runs`（api 直连唤醒，秒到）
而 watcher（`buzz-inbox-watcher.sh`，<=5min）按**行号 vs dispatched 游标**判断新信，
并不看 api 通道做过什么。于是同一单被唤醒两次（实证 2026-10-07：03:36:17 api 投第 8 单
= 收件箱第 44 行；03:50:01 watcher `RESERVE range=44..44 prev_dispatched=43` -> COMMIT）。

改动前这台闸只装在 watcher 侧：api 通道对它是**透明**的（属契约层约定，非机器强制）。
本模块把 api 侧也接进**同一个** claim（同一 flock 锁文件 + 同一 `dispatched` 游标）——
共享状态 = 幂等键，两侧天然互斥，无需新增第三个状态机。

## 语义（状态可判 · 非静默）

| 输出 | 含义 | api 侧动作 |
|---|---|---|
| `issued`   | 认领成功（dispatched 已原子抬到区间末端） | 放行 run，受理后 `commit` |
| `rejected` | 该行**已被派发/他人持有**（rc=1 无增量 / rc=2 HELD） | **拒唤醒**：HTTP 409 + 台账行（出声，不静默丢） |
| `degraded` | 认领器缺失 / rc=3 环境错 / 输出不可解析 | **放行**（闸故障不停摆）并出声 |

## 边界（已知 · 别把它当万灵药）

- **只挡重复「认领」**（同一信封被两条通道各唤醒一次）。
  **不挡**：同一信封在单通道内被重复处理、watcher 自身重跑、TTL 接管后的二次进入。
- **只对带 `metadata.inbox_line` 的请求生效**。不带该字段的 api 调用（用户/前端直接
  `POST /v1/runs`）**完全不触碰 claim**，行为与改动前一致（保护「api 单通道投递成功率」）。
- 认领后 run 崩溃（SIGKILL 不跑 abort）=> 认领靠 TTL(300s) 过期后由 watcher 接管，
  区间进 watcher 唤醒序列，**不死信**。
- 判据口径是**行号区间**；闸随 env `BUZZ_INBOX_MIMIR*` 走（沙箱只覆写 dispatcher 路径即全隔离）。

## 闸拒时看什么读数

1. `~/.mimiraether/data/ops/api_claim_gate.jsonl`（本闸台账，逐次决策）
2. `<dispatched>.claim.log`（认领器共享台账：RESERVE / HELD / COMMIT / ABORT）
3. HTTP 409 body（`code="inbox_line_already_claimed"`）
4. `python3 ~/.mimiraether/scripts/buzz_inbox_claim.py show`（三游标 + 当前 claim）
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from os import environ as ENV
from os import makedirs, path as opath
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 与 watcher.sh 同一默认值（两侧必须指向同一认领器，否则闸退化回契约层）
DEFAULT_CLAIM_TOOL = "/home/rayliu/.mimiraether/scripts/buzz_inbox_claim.py"


def _home() -> str:
    return ENV.get("MIMIR_AETHER_HOME") or (opath.expanduser("~") + "/.mimiraether")


def claim_tool_path() -> str:
    """认领器路径（env 可覆写 —— 沙箱/测试用）。"""
    return ENV.get("BUZZ_INBOX_MIMIR_CLAIM_TOOL") or DEFAULT_CLAIM_TOOL


def gate_log_path() -> str:
    return ENV.get("BUZZ_INBOX_CLAIM_GATE_LOG") or (_home() + "/data/ops/api_claim_gate.jsonl")


def parse_inbox_line(metadata: Optional[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
    """把 `metadata.inbox_line` 解析成 (start, end)；无该字段/invalid => None。

    接受五种形态（派单方手写方便；机器只认这五种，不做模糊猜测）：
        44 | "44" | "44..44" | "44-44"        -> (44, 44)
        [44, 45] / {"line": 44} / {"start": 44, "end": 45}
    """
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("inbox_line")
    if raw is None:
        raw = metadata.get("inbox_lines")
    if raw is None:
        return None
    try:
        if isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            start = end = raw
        elif isinstance(raw, str):
            s = raw.strip().replace("..", "-").replace("~", "-")
            if "-" in s:
                a, b = s.split("-", 1)
                start, end = int(a), int(b)
            else:
                start = end = int(s)
        elif isinstance(raw, dict):
            if "line" in raw:
                start = end = int(raw["line"])
            else:
                start, end = int(raw["start"]), int(raw.get("end", raw["start"]))
        elif isinstance(raw, (list, tuple)) and len(raw) == 2:
            start, end = int(raw[0]), int(raw[1])
        else:
            return None
    except (TypeError, ValueError):
        return None
    if start <= 0 or end < start:
        return None
    return start, end


def _log_gate(row: Dict[str, Any]) -> None:
    """闸台账（append-only JSONL）。写失败不致命，但要出声。"""
    try:
        path = gate_log_path()
        d = opath.dirname(path)
        if d:
            makedirs(d, exist_ok=True)
        row.setdefault("ts", time.time())
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:      # pragma: no cover - 环境异常路径
        logger.warning("[inbox_claim_gate] 台账写入失败 %s: %s", gate_log_path(), exc)


def _parse_claimed(out: str) -> Optional[Tuple[int, int]]:
    """从 `CLAIMED <owner> <start> <end> [prev_dispatched=N] | ...` 取区间。"""
    for line in (out or "").splitlines():
        parts = line.split()
        if parts and parts[0] in ("CLAIMED", "TAKEOVER") and len(parts) >= 4:
            try:
                return int(parts[2]), int(parts[3])
            except ValueError:
                continue
    return None


@dataclass
class ClaimDecision:
    """三态：issued / rejected / degraded（rejected 时必带可读 reason）。"""

    state: str = "none"
    reason: str = ""
    start: int = 0
    end: int = 0
    rc: Optional[int] = None
    detail: str = ""
    env: Dict[str, str] = field(default_factory=dict)

    @property
    def rejected(self) -> bool:
        return self.state == "rejected"

    @property
    def owner(self) -> str:
        return self.env.get("owner", "")

    def readout(self) -> str:
        return ("state=%s rc=%s range=%s..%s reason=%s detail=%s"
                % (self.state, self.rc, self.start, self.end, self.reason, self.detail[:200]))


def _run_claim(args, env: Dict[str, str], timeout: float = 15.0):
    tool = claim_tool_path()
    if not opath.exists(tool):
        return None, "claim tool missing: %s" % tool
    try:
        p = subprocess.run(
            ["python3", tool] + list(args),
            capture_output=True, text=True, timeout=timeout,
            env=dict(ENV, **env),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, "claim tool exec error: %s" % exc
    return p, ((p.stdout or "") + (p.stderr or "")).strip()


def claim_for_api_run(run_id: str, metadata: Optional[Dict[str, Any]]) -> ClaimDecision:
    """api 直连通道唤醒前先走同一套认领；返回三态决策。

    调用点在 `api_server._handle_runs`（建 run 之前）。**不受理则必须可见拒**。
    """
    rng = parse_inbox_line(metadata)
    if rng is None:
        return ClaimDecision(state="none", reason="no inbox_line declared")

    start, end = rng
    owner = "api-%s" % run_id
    env = {"owner": owner}
    p, text = _run_claim(["reserve", "--owner", owner], env)

    if p is None:
        d = ClaimDecision(state="degraded", reason="claim tool unavailable",
                          start=start, end=end, rc=None, detail=text or "", env=env)
        logger.warning("[inbox_claim_gate] DEGRADED run_id=%s %s => 放行（闸故障不阻派发）",
                       run_id, d.readout())
        _log_gate({"event": "degraded", "run_id": run_id, "declared": [start, end],
                   "detail": text or ""})
        return d

    rc = p.returncode
    if rc == 0:
        got = _parse_claimed(text)
        if got is None:
            d = ClaimDecision(state="degraded", reason="unparseable CLAIMED output",
                              start=start, end=end, rc=rc, detail=text, env=env)
            logger.warning("[inbox_claim_gate] DEGRADED run_id=%s %s => 放行", run_id, d.readout())
            _log_gate({"event": "degraded", "run_id": run_id, "declared": [start, end],
                       "detail": text[:300]})
            return d
        d = ClaimDecision(state="issued", reason="claimed", start=got[0], end=got[1],
                          rc=rc, detail=text, env=env)
        logger.info("[inbox_claim_gate] ISSUED run_id=%s owner=%s range=%d..%d（declared %d..%d）",
                    run_id, owner, got[0], got[1], start, end)
        _log_gate({"event": "issued", "run_id": run_id, "owner": owner,
                   "range": [got[0], got[1]], "declared": [start, end],
                   "claim_log": text.splitlines()[0] if text else ""})
        return d

    if rc == 1:
        reason = "no increment (line already dispatched by the other channel)"
    elif rc == 2:
        reason = "held by another owner"
    else:
        d = ClaimDecision(state="degraded", reason="claim rc=%s" % rc, start=start, end=end,
                          rc=rc, detail=text, env=env)
        logger.warning("[inbox_claim_gate] DEGRADED run_id=%s %s => 放行", run_id, d.readout())
        _log_gate({"event": "degraded", "run_id": run_id, "declared": [start, end],
                   "rc": rc, "detail": text[:300]})
        return d

    d = ClaimDecision(state="rejected", reason=reason, start=start, end=end, rc=rc,
                      detail=text, env=env)
    # 出声：日志 + 台账双落，禁静默丢弃（老病）
    logger.warning("[inbox_claim_gate] REJECTED run_id=%s %s（该行已被另一通道消费）",
                   run_id, d.readout())
    _log_gate({"event": "rejected", "run_id": run_id, "declared": [start, end],
               "rc": rc, "reason": reason, "claim_log": text.splitlines()[0] if text else ""})
    return d


def commit_api_claim(decision: ClaimDecision) -> None:
    """run 已被受理（202）=> 认领落地（清 claim 记录 + 写共享台账行）。"""
    if decision.state != "issued":
        return
    p, text = _run_claim(["commit", "--owner", decision.owner], decision.env)
    ok = bool(p is not None and p.returncode == 0)
    if not ok:
        logger.warning("[inbox_claim_gate] COMMIT 失败 owner=%s detail=%s（认领仍由 dispatched 兜底）",
                       decision.owner, (text or "")[:200])
    _log_gate({"event": "commit", "owner": decision.owner, "ok": ok,
               "range": [decision.start, decision.end], "detail": (text or "")[:200]})


def abort_api_claim(decision: ClaimDecision) -> None:
    """run 未被受理时回滚认领（供未来异常路径用）。"""
    if decision.state != "issued":
        return
    p, text = _run_claim(["abort", "--owner", decision.owner], decision.env)
    _log_gate({"event": "abort", "owner": decision.owner,
               "ok": bool(p is not None and p.returncode == 0), "detail": (text or "")[:200]})
