"""verification_ledger.py — `data/verification_results.jsonl` 的生产端 + 显式 N/A 读口（R2 修复）。

R2（总表 2026-09-18 行 298）病灶：
  · 该量具 **从未被创建过**（不是被删）——全仓 0 个写端；
  · 「应该记录」只写在 dormant 技能的散文祈使句里
    （`skills/.dormant/mimiraether/mimiraether-verification/SKILL.md` 第 4 步「记录日志」）；
  · 而既有读端都写着 `if not log_path.exists(): return 0 / {"total": 0}`
    ⇒ **「无数据」被伪装成「无失败」**（假绿，与 feedback_events 停更 5 周同族）。

本模块 = 单点（写 + 读），落地 R2 的 DoD「建该文件 或 改技能读取口径」：
  · 生产端：`record_verification_result()` —— 由 verify-before-report 守卫的判定入口
    `agent.verify_before_report_guard.evaluate_finish()` 调用（接线点：`agent/agent_loop.py`
    的 verify-before-report 分支），**每次真实判定记一条**（有声明才记，防刷量）。
  · 读口：`read_ledger_status()` / `verification_failure_stats()` / `repeat_tool_calls()` /
    `verification_reliability()` —— **无数据 ⇒ 显式 N/A**（`status="no_data"` / `n_a=True` /
    `None` + WARNING），**绝不返回 0 充当读数**（R2 硬约束：无数据 ≠ 无失败）。

记录 schema（与既有三个读端逐键兼容：`passed` / `failure_type` / `timestamp` / `tool` / `message`）：

    {"timestamp": "2026-09-21T01:00:00+00:00", "passed": false,
     "failure_type": "claim_without_verification", "tool": "",
     "message": "...", "claim": "...", "user": "...", "source": "verify_before_report_guard"}

env：
  `MIMIR_VERIFICATION_LEDGER=0`       ⇒ 停写（默认 `1` 开启；读口不受它影响）
  `MIMIR_VERIFICATION_RESULTS_PATH=…` ⇒ 覆盖落盘路径（测试/演练用）

CLI（真实读数，自评/审计复算用）：

    .venv/bin/python3 -m agent.verification_ledger --status
    .venv/bin/python3 -m agent.verification_ledger --status --json
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

LEDGER_RELPATH: tuple[str, ...] = ("data", "verification_results.jsonl")
LEDGER_ENV_PATH = "MIMIR_VERIFICATION_RESULTS_PATH"
LEDGER_ENV_ENABLE = "MIMIR_VERIFICATION_LEDGER"
NO_DATA_SEMANTICS = "no_data != no_failure"  # 无数据 ≠ 无失败

_MESSAGE_MAX = 300
_CLAIM_MAX = 200
_USER_MAX = 200

_warned: set[str] = set()


# ===========================================================================
# 路径 / 开关
# ===========================================================================

def ledger_path() -> Path:
    """量具落盘路径（每次调用重读环境，保证 pytest tmp home / 覆盖件生效）。

    真源 = `mimir_constants.get_mimir_home()`（env 逐次解析：MIMIR_AETHER_HOME /
    MIMIRAETHER_HOME / HERMES_HOME / 默认 ~/.mimiraether）——**不**用
    `Path.home()/".mimiraether"` 拼路径（本机 HOME 即 mimir home ⇒ 会得到嵌套假路径）。
    """
    override = os.environ.get(LEDGER_ENV_PATH, "").strip()
    if override:
        return Path(override)
    try:
        from mimir_constants import get_mimir_home

        home = Path(get_mimir_home())
    except Exception:  # pragma: no cover - 独立脚本/异常环境
        home = Path(os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether"))
    return home.joinpath(*LEDGER_RELPATH)


def ledger_enabled() -> bool:
    """写侧开关（默认开）。读侧不受它影响 —— 停写不能把已有数据读成 0。"""
    return os.environ.get(LEDGER_ENV_ENABLE, "1") == "1"


def _clip(text: Any, limit: int) -> str:
    if text is None:
        return ""
    s = text if isinstance(text, str) else str(text)
    return s[:limit]


def _warn_once(target: Path, reason: str) -> None:
    key = str(target)
    if key in _warned:
        return
    _warned.add(key)
    logger.warning("[verification-ledger] %s", reason)


# ===========================================================================
# 写侧（生产端）
# ===========================================================================

def record_verification_result(
    *,
    passed: bool,
    failure_type: Optional[str] = None,
    tool: str = "",
    message: str = "",
    claim: str = "",
    user: str = "",
    source: str = "verify_before_report_guard",
    extra: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """追加一条验证判定记录。

    契约：**纯加法** —— 任何异常只打 WARNING，绝不抛出（守卫语义不变量：
    量具写失败不得影响被观测的守卫判定）。返回落盘 entry；停写/失败返回 `None`。
    """
    if not ledger_enabled():
        return None

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": bool(passed),
        "failure_type": failure_type,
        "tool": _clip(tool, 60),
        "message": _clip(message, _MESSAGE_MAX),
        "source": _clip(source, 60),
        "claim": _clip(claim, _CLAIM_MAX),
        "user": _clip(user, _USER_MAX),
    }
    if extra:
        entry.update(extra)

    try:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry
    except Exception as exc:  # 纯加法：量具写失败不影响主路径
        logger.warning("[verification-ledger] append failed (%s): %s", ledger_path(), exc)
        return None


# ===========================================================================
# 读侧（显式 N/A —— 无数据 ≠ 无失败）
# ===========================================================================

def read_records(path: Optional[Path] = None) -> tuple[list[dict[str, Any]], int]:
    """读全部记录；返回 (有效记录, 损坏行数)。坏行被计数，不静默丢弃。"""
    target = Path(path) if path is not None else ledger_path()
    records: list[dict[str, Any]] = []
    corrupt = 0
    with open(target, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                corrupt += 1
                continue
            if isinstance(obj, dict):
                records.append(obj)
            else:
                corrupt += 1
    return records, corrupt


def read_ledger_status(path: Optional[Path] = None) -> dict[str, Any]:
    """量具存活状态 —— 「无数据 ≠ 无失败」的唯一判据来源。"""
    target = Path(path) if path is not None else ledger_path()
    base: dict[str, Any] = {
        "path": str(target),
        "semantics": NO_DATA_SEMANTICS,
        "exists": False,
        "n_a": True,
        "status": "no_data",
        "reason": "",
        "lines": 0,
        "valid": 0,
        "corrupt": 0,
        "last_timestamp": None,
    }
    if not target.exists():
        base["reason"] = (
            f"量具缺失：{target} 不存在（无生产端产出）—— 无数据 ≠ 无失败，不得读作 0 失败"
        )
        _warn_once(target, base["reason"])
        return base

    try:
        records, corrupt = read_records(target)
    except Exception as exc:
        base["status"] = "unreadable"
        base["reason"] = f"量具不可读：{target}（{exc}）—— 无数据 ≠ 无失败"
        _warn_once(target, base["reason"])
        return base

    base["exists"] = True
    base["valid"] = len(records)
    base["corrupt"] = corrupt
    base["lines"] = len(records) + corrupt
    if not records:
        base["status"] = "no_data"
        base["reason"] = (
            f"量具空或全损坏：{target}（valid=0, corrupt={corrupt}）—— "
            "无数据 ≠ 无失败，不得读作 0 失败"
        )
        _warn_once(target, base["reason"])
        return base

    base["status"] = "ok"
    base["n_a"] = False
    base["reason"] = f"量具存活：{len(records)} 条有效记录（corrupt={corrupt}）"
    base["last_timestamp"] = records[-1].get("timestamp")
    return base


# ── 既有三个读端（dormant mimiraether-self_evolution 散文版）的 R2 版实现 ──
# 差别只有一处：**无数据 ⇒ N/A（None），不是 0**。

def verification_failure_stats(path: Optional[Path] = None) -> dict[str, Any]:
    """验证失败统计。

    有数据：`{"status": "ok", "n_a": False, "total": int, "by_type": {...}}`
    无数据：`{"status": "no_data", "n_a": True, "total": None, "by_type": None,
             "reason": "…无数据 ≠ 无失败"}`
    """
    status = read_ledger_status(path)
    out: dict[str, Any] = {
        "status": status["status"],
        "n_a": status["n_a"],
        "reason": status["reason"],
        "total": None,
        "by_type": None,
        "samples": status["valid"],
        "ledger_path": status["path"],
        "semantics": NO_DATA_SEMANTICS,
    }
    if status["status"] != "ok":
        return out
    records, _ = read_records(Path(status["path"]))
    total = 0
    by_type: dict[str, int] = {}
    for entry in records:
        if not entry.get("passed", True):
            total += 1
            ftype = entry.get("failure_type") or "unknown"
            by_type[ftype] = by_type.get(ftype, 0) + 1
    out["total"] = total
    out["by_type"] = by_type
    return out


def repeat_tool_calls(path: Optional[Path] = None) -> dict[str, Any]:
    """同一工具在「声明判定记录」中出现的最大次数（旧 `_count_repeat_tool_calls` 的 R2 版）。

    口径缺口（如实登记）：旧读端口径就是「按 tool 字段计数取 max」，本版保持一致；
    它**不是**「同一 run 内重复调用同一工具」的精确度量 —— 精确度量需要 run 级分组键，
    当前 schema 无该键（不擅自改语义）。
    无数据 ⇒ `max_repeat = None`（**不是 0**）。
    """
    status = read_ledger_status(path)
    out: dict[str, Any] = {
        "status": status["status"],
        "n_a": status["n_a"],
        "reason": status["reason"],
        "max_repeat": None,
        "by_tool": None,
        "semantics": NO_DATA_SEMANTICS,
    }
    if status["status"] != "ok":
        return out
    records, _ = read_records(Path(status["path"]))
    calls: dict[str, int] = {}
    for entry in records:
        tool = entry.get("tool") or "unknown"
        calls[tool] = calls.get(tool, 0) + 1
    out["by_tool"] = calls
    out["max_repeat"] = max(calls.values(), default=0)
    return out


def verification_reliability(path: Optional[Path] = None) -> dict[str, Any]:
    """验证可靠性估计（旧 `_estimate_verification_reliability` 的 R2 版）。

    无数据 ⇒ `reliability_score = None` + `sample_quality = "n/a"`。
    旧版回落 0.5 —— 那是**伪造一个中间读数**，本版不再这么做。
    """
    status = read_ledger_status(path)
    out: dict[str, Any] = {
        "status": status["status"],
        "n_a": status["n_a"],
        "reason": status["reason"],
        "reliability_score": None,
        "sample_quality": "n/a",
        "confidence_interval": "n/a (no data)",
        "total_samples": None,
        "semantics": NO_DATA_SEMANTICS,
    }
    if status["status"] != "ok":
        return out
    records, _ = read_records(Path(status["path"]))
    window = min(len(records), 20)
    samples = records[-window:]
    weights = [0.5 + 0.5 * (i / window) for i in range(window)]
    total_weight = sum(weights)
    passed_weight = sum(
        weights[i] for i, sample in enumerate(samples) if sample.get("passed", True)
    )
    reliability = passed_weight / total_weight if total_weight else 0.0
    margin = 0.5 / (window ** 0.5 + 1)
    out["reliability_score"] = round(reliability, 3)
    out["sample_quality"] = "high" if window >= 20 else ("medium" if window >= 10 else "low")
    out["confidence_interval"] = (
        f"{max(0.0, reliability - margin):.3f}-{min(1.0, reliability + margin):.3f}"
    )
    out["total_samples"] = len(records)
    return out


def collect_verification_metrics(path: Optional[Path] = None) -> dict[str, Any]:
    """四读端一次性汇总（自评 `collect_metrics` 的 R2 接入点）。"""
    return {
        "ledger": read_ledger_status(path),
        "verification": verification_failure_stats(path),
        "repeat_tool_calls": repeat_tool_calls(path),
        "reliability": verification_reliability(path),
    }


# ===========================================================================
# CLI —— 真实读数（自评/复算）
# ===========================================================================

def _main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="verification_results.jsonl 量具读数（无数据 ⇒ N/A，不报 0）"
    )
    parser.add_argument("--status", action="store_true", help="打印量具状态 + 四读端汇总")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    payload = collect_verification_metrics()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        st = payload["ledger"]
        print(f"ledger_path : {st['path']}")
        print(f"status      : {st['status']}  (n_a={st['n_a']})")
        print(f"reason      : {st['reason']}")
        print(f"valid/corrupt/lines : {st['valid']}/{st['corrupt']}/{st['lines']}")
        print(f"failures    : {payload['verification']['total']}"
              f"  by_type={payload['verification']['by_type']}")
        print(f"repeat_tool : {payload['repeat_tool_calls']['max_repeat']}")
        print(f"reliability : {payload['reliability']['reliability_score']}"
              f"  quality={payload['reliability']['sample_quality']}")
        print(f"semantics   : {st['semantics']}  (无数据 ≠ 无失败)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
