#!/usr/bin/env python3
"""P0 chroma 索引健康监控 —— 报告层（零 LLM · B2/P0-B script 形态 · 2026-09-26）。

为什么有这一层（根因，不是洁癖）：
    本监控原为 **agent 形态**（`script: None` + 一段 prompt）。2026-09-22 20:00 起
    上游 402 使 agent run 只返回 49 字节的故障兜底文本，而台账仍记
    `last_status=ok` / `last_delivery_ok=true` —— 「调度在跑、投递在跑、检查没跑」，
    且两条不同 job（chroma 与 wiki-quality）拿到**逐字节相同的 49 字节**
    ⇒ 与 job 语义无关。这是「坏消息长得像好消息」的假绿族。
    改成 script 形态有三个直接收益：**零 LLM**（不再有 402 暴露面、省 6 次 run/日）、
    **判据在盘上可复算**、**失败真的改退出码**。

    本脚本是**报告层**，不重复实现检测：检测仍在 `p0_index_monitor.py`
    （它写 `data/p0_index_health.json`）。这里把它们翻译成一句人话 + 一个退出码。

口径自曝（别把这些当强判据）：
    * `garbage_in_index` 只扫前 5000 条（`garbage_scan_scanned`），**不是全量**；
      报告里显式打印覆盖率，避免「零垃圾」被外推到 2 万条索引。
    * `incremental_enabled` 读的是 **env 标志**，不是行为证明。
    * 索引新鲜度用 `chroma.sqlite3` 的 mtime 与源库最新消息时间戳作**代理**：
      chroma 任何写入都会推 mtime，因此这是「上一次写入 vs 最新源数据」的比较，
      不是「某条消息已被索引」的证明。
    * 漂移阈值沿用监控本体：`max(10, 2% × 可索引数)`。

退出码：0 = 健康（打一行心跳）· 2 = 异常（打明细）· 0 = 监控未产出也算异常？**不**
    —— 监控未产出同样走 2：它是最该被听见的一种。缺文件与陈旧文件都算。

零 LLM：本文件不 import 任何模型客户端。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_INTERVAL_HOURS = 6
# 监控心跳容忍度：超过 2 个调度周期没有新产出 = 监控停摆（不是索引病）
HEARTBEAT_TOLERANCE_FACTOR = 2
# 索引落后源数据的容忍度（秒）。600s 覆盖一次 6h 周期内的正常写入间隔。
INDEX_LAG_TOLERANCE_S = 600
DRIFT_ABS_FLOOR = 10
DRIFT_REL = 0.02


def _mimir_home() -> Path:
    """与运行时同一真源；import 失败退回环境变量/约定路径（CI 可用）。"""
    try:
        from mimir_constants import get_mimir_home  # type: ignore

        return Path(get_mimir_home())
    except Exception:
        env = os.environ.get("MIMIR_AETHER_HOME")
        if env:
            return Path(env)
        return Path.home() / ".mimiraether"


def _parse_ts(raw: str) -> _dt.datetime | None:
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def _newest_source_ts(db_path: Path) -> float | None:
    """Newest message timestamp in the search DB, as epoch seconds."""
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
        try:
            row = next(conn.execute("SELECT MAX(timestamp) FROM messages"))
        finally:
            conn.close()
    except Exception:
        return None
    if not row or row[0] is None:
        return None
    try:
        return float(row[0])
    except (TypeError, ValueError):
        return None


def evaluate(
    health: dict | None,
    *,
    now: _dt.datetime,
    health_mtime: float | None,
    chroma_mtime: float | None,
    newest_source_ts: float | None,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
) -> tuple[bool, list[str], str]:
    """Return (healthy, problems, heartbeat_line). Pure — no I/O, so it is testable."""
    problems: list[str] = []
    checks = (health or {}).get("checks", {}) if health else {}

    if not health:
        problems.append("监控本体未产出 health JSON（检测层没跑或写盘失败）")
        return False, problems, ""

    if health_mtime is not None:
        age_h = (now.timestamp() - health_mtime) / 3600.0
        if age_h > HEARTBEAT_TOLERANCE_FACTOR * interval_hours:
            problems.append(
                "监控本身停摆：health JSON 已 %.1fh 未更新（容忍 %.0fh）"
                % (age_h, HEARTBEAT_TOLERANCE_FACTOR * interval_hours)
            )

    if not health.get("ok", False):
        for key, label in (
            ("source_error", "源库读取失败"),
            ("chroma_error", "chroma 读取失败"),
            ("garbage_scan_error", "垃圾扫描失败"),
        ):
            if checks.get(key):
                problems.append("%s：%s" % (label, str(checks[key])[:160]))

    src = checks.get("source_indexable")
    docs = checks.get("chroma_docs")
    drift = None
    if isinstance(src, int) and isinstance(docs, int):
        drift = docs - src
        allowed = max(DRIFT_ABS_FLOOR, int(src * DRIFT_REL))
        if abs(drift) > allowed:
            problems.append("漂移 %+d 超过阈值 %d（chroma %d vs 源 %d）" % (drift, allowed, docs, src))

    garbage = checks.get("garbage_in_index")
    scanned = checks.get("garbage_scan_scanned")
    if isinstance(garbage, int) and garbage > 0:
        problems.append("索引内垃圾 %d 条（>0 = 垃圾回潮）" % garbage)

    if checks.get("backfill_phase") not in (None, "done"):
        problems.append("backfill 阶段未完成：%s" % checks.get("backfill_phase"))
    if checks.get("backfill_phase") == "missing":
        problems.append("backfill 进度文件缺失")

    if chroma_mtime is not None and newest_source_ts is not None:
        lag = chroma_mtime - newest_source_ts
        if lag < -INDEX_LAG_TOLERANCE_S:
            problems.append(
                "索引落后源数据 %.0f 分钟（chroma 末次写入早于最新消息）" % (abs(lag) / 60.0)
            )

    coverage = ""
    if isinstance(scanned, int) and isinstance(docs, int) and docs:
        coverage = "扫描覆盖=%.0f%%" % (100.0 * scanned / docs)
    parts = ["docs=%s" % (docs if docs is not None else "?")]
    if drift is not None:
        parts.append("漂移=%+d" % drift)
    parts.append("垃圾=%s" % (garbage if garbage is not None else "?"))
    if coverage:
        parts.append(coverage)
    heartbeat = "[索引健康] ✅ %s · %s" % (
        now.astimezone().strftime("%Y-%m-%d %H:%M"),
        " · ".join(parts),
    )
    return (not problems), problems, heartbeat


def run(args: argparse.Namespace) -> int:
    health_path = Path(args.health_file) if args.health_file else _mimir_home() / "data" / "p0_index_health.json"
    chroma_path = (
        Path(args.chroma_file) if args.chroma_file else _mimir_home() / "data" / "chroma_sessions" / "chroma.sqlite3"
    )
    db_path = Path(args.source_db) if args.source_db else _mimir_home() / "data" / "sessions_search.db"

    now = _parse_ts(args.now) if args.now else _dt.datetime.now(_dt.timezone.utc)
    assert now is not None

    health = None
    health_mtime = None
    if health_path.is_file():
        health_mtime = health_path.stat().st_mtime
        try:
            health = json.loads(health_path.read_text(encoding="utf-8"))
        except Exception as exc:  # a corrupt file is a finding, not a crash
            print("[索引健康] 🔴 health JSON 无法解析：%s" % str(exc)[:160])
            return 2

    healthy, problems, heartbeat = evaluate(
        health,
        now=now,
        health_mtime=health_mtime,
        chroma_mtime=chroma_path.stat().st_mtime if chroma_path.is_file() else None,
        newest_source_ts=_newest_source_ts(db_path),
        interval_hours=args.interval_hours,
    )

    if healthy:
        print(heartbeat)
        return 0

    print("[索引健康] 🔴 %d 项异常 · %s" % (len(problems), now.astimezone().strftime("%Y-%m-%d %H:%M")))
    for item in problems:
        print("  - %s" % item)
    if health:
        checks = health.get("checks", {})
        print(
            "  原始读数：checked_at=%s source=%s chroma=%s 垃圾=%s/%s 阶段=%s 增量标志=%s"
            % (
                health.get("checked_at"),
                checks.get("source_indexable"),
                checks.get("chroma_docs"),
                checks.get("garbage_in_index"),
                checks.get("garbage_scan_scanned"),
                checks.get("backfill_phase"),
                checks.get("incremental_enabled"),
            )
        )
    print("  建议：① 先确认监控本体是否在跑（health JSON 的 checked_at）② 漂移/垃圾需人工判性质，勿自动回填")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0 chroma index health report (zero LLM)")
    parser.add_argument("--health-file", default=None)
    parser.add_argument("--chroma-file", default=None)
    parser.add_argument("--source-db", default=None)
    parser.add_argument("--now", default=None, help="ISO8601 override (tests)")
    parser.add_argument("--interval-hours", type=int, default=DEFAULT_INTERVAL_HOURS)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
