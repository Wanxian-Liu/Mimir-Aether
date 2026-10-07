#!/usr/env python3
"""F2 · run_health 告警台账读口（第 8 单 · 跨通道出声通道 · 2026-10-07）。

## 病灶（盘上实证）
`agent/run_health.py` 越线时 append `data/ops/run_health_alerts.jsonl`，但**无外部消费者**
⇒ 「只写字段、无人被告知」：告警躺在 jsonl 里，外部要发现它必须人工打开文件 ⇒
出声面不成立（读数：`grep -rln 'run_health_alerts' --include=*.py .` 仅命中
`agent/run_health.py` + 其测试）。

## 本脚本（纯读口 · 不在 run_health 模块内）
读 `data/ops/run_health_alerts.jsonl`，给出**可判读数**（stdout 明示 + rc 语义）：

| rc | 语义 | stdout 首行形态 |
|---|---|---|
| 0 | 无告警 | `RUN_HEALTH_ALERTS: NONE ...` |
| 2 | 有告警 | `RUN_HEALTH_ALERTS: ALERT n=<N> ...` |
| 3 | 台账缺失 / 不可读（出声通路断了） | `RUN_HEALTH_ALERTS: MISSING <path>` |
| 4 | 解析失败（坏行 > 0） | `RUN_HEALTH_ALERTS: PARSE_ERROR bad=<n> ...` |

**错误语义不可裁剪**：缺文件 != 无告警 != 有告警 != 坏行 —— 四态各自明示，
**禁空白静默**（无告警必须打印 NONE，不得 stdout 为空）。
优先级：UNREADABLE(3) > PARSE_ERROR(4) > ALERT(2) > NONE(0)。

## 用法
    python3 scripts/check_run_health_alerts.py                 # 全量台账
    python3 scripts/check_run_health_alerts.py --since 24h     # 只看最近 24h
    python3 scripts/check_run_health_alerts.py --json          # 机器可读

## 回滚
本脚本**纯只读**：不写盘、不改 state、不发网络、不 import agent.run_health
（独立消费者，防自我循环）—— 删除本文件即回滚。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RC_NONE = 0
RC_ALERTS = 2
RC_UNREADABLE = 3
RC_PARSE_ERROR = 4
# SKIP / NO_ALERTS_YET 同 rc 0（通路健康、只是无可报之事）——但**状态名不同**，
# 目的是让「从未告警」与「通路断了」在 stdout 上可分辨（禁把二者读成一回事）。


def mimir_home() -> Path:
    """与 agent/run_health.py 同源取 Mimir 家（但不 import 该模块）。"""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from mimir_constants import get_mimir_home  # type: ignore

        return Path(get_mimir_home())
    except Exception:
        env_home = os.environ.get("MIMIR_AETHER_HOME") or os.environ.get("MIMIR_HOME")
        if env_home:
            return Path(env_home)
        return Path(os.path.expanduser("~/.mimiraether"))


def alert_path() -> Path:
    return mimir_home() / "data" / "ops" / "run_health_alerts.jsonl"


def parse_window(spec: str) -> Optional[_dt.timedelta]:
    """`24h` / `90m` / `7d` -> timedelta；空 / `all` -> None。"""
    s = (spec or "").strip().lower()
    if not s or s == "all":
        return None
    unit, num = s[-1], s[:-1]
    try:
        val = float(num)
    except Exception:
        raise SystemExit("bad --since: %r (use e.g. 24h / 90m / 7d)" % spec)
    if unit == "h":
        return _dt.timedelta(hours=val)
    if unit == "m":
        return _dt.timedelta(minutes=val)
    if unit == "d":
        return _dt.timedelta(days=val)
    raise SystemExit("bad --since unit: %r (h/m/d)" % spec)


def read_alerts(path: Path) -> Tuple[List[Dict[str, Any]], List[int], Optional[str]]:
    """-> (records, bad_line_numbers, error)。

    error 取值：None（读到东西）/ `missing`（文件不存在）/
    `unreadable: <Exc>`（权限/IO）。**三态互斥且各自明示**（禁静默）。
    """
    if not path.exists():
        return [], [], "missing"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except Exception as exc:
        return [], [], "unreadable: %s: %s" % (type(exc).__name__, exc)
    recs: List[Dict[str, Any]] = []
    bad: List[int] = []
    for i, raw in enumerate(lines, start=1):
        s = raw.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            bad.append(i)
            continue
        if not isinstance(obj, dict):
            bad.append(i)
            continue
        recs.append(obj)
    return recs, bad, None


def _ts(rec: Dict[str, Any]) -> Optional[_dt.datetime]:
    try:
        return _dt.datetime.fromisoformat(str(rec.get("ts") or ""))
    except Exception:
        return None


def select(
    recs: List[Dict[str, Any]],
    window: Optional[_dt.timedelta],
    now: Optional[_dt.datetime] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """窗口过滤 -> (kept, undated_n)。`window is None` ⇒ 全量、undated=0。"""
    if window is None:
        return list(recs), 0
    ref = now or _dt.datetime.now()
    cutoff = ref - window
    kept: List[Dict[str, Any]] = []
    undated = 0
    for r in recs:
        t = _ts(r)
        if t is None:
            undated += 1
            continue
        if t >= cutoff:
            kept.append(r)
    return kept, undated


def missing_diagnosis(home: Path) -> Tuple[str, str]:
    """台账缺失时进一步分辨（**既防假红也防假绿**）：

    - `SKIP`          : home 目录不存在 ⇒ 非 Mimir 主机（CI）⇒ 不假红
    - `NO_ALERTS_YET` : state 在盘且**从未** fire 过告警 ⇒ 台账尚未创建（合法）
    - `MISSING`       : 其余 ⇒ 出声通路断了（state 缺 / 不可解析 / 已 fire 过）
    """
    if not home.exists():
        return "SKIP", "非 Mimir 主机：home 目录不存在（%s）⇒ 跳过，不假红" % home
    state = home / "data" / "ops" / "run_health_state.json"
    if not state.exists():
        return "MISSING", "台账与 state 快照双缺（%s）⇒ 出声通路断了" % state
    try:
        st = json.loads(state.read_text(encoding="utf-8"))
    except Exception as exc:
        return "MISSING", "state 不可解析（%s: %s）⇒ 出声通路断了" % (type(exc).__name__, exc)
    alerted = st.get("alerted") if isinstance(st, dict) else None
    fired = 0
    if isinstance(alerted, dict):
        fired = sum(1 for v in alerted.values() if isinstance(v, dict) and any(v.values()))
    if fired:
        return "MISSING", "state 记录已 fire %d 次告警但台账缺失 ⇒ 出声通路断了" % fired
    return "NO_ALERTS_YET", "state 在盘且从未 fire 过告警 ⇒ 台账尚未创建（合法，非故障）"


def summarize(
    recs: List[Dict[str, Any]],
    bad: List[int],
    err: Optional[str],
    *,
    path: Path,
    since: str,
    undated: int = 0,
) -> Dict[str, Any]:
    """pure：把读口读数折成一个 dict（stdout 与 --json 共用，防两处口径漂移）。"""
    by_kind: Dict[str, int] = {}
    latest: Optional[Tuple[_dt.datetime, Dict[str, Any]]] = None
    for r in recs:
        k = str(r.get("kind") or "?")
        by_kind[k] = by_kind.get(k, 0) + 1
        t = _ts(r)
        if t is not None and (latest is None or t > latest[0]):
            latest = (t, r)
    if err == "missing":
        state = "MISSING"
    elif err:
        state = "UNREADABLE"
    elif bad:
        state = "PARSE_ERROR"
    elif recs:
        state = "ALERT"
    else:
        state = "NONE"
    return {
        "state": state,
        "path": str(path),
        "since": since,
        "n": len(recs),
        "by_kind": by_kind,
        "bad_lines": bad,
        "undated": undated,
        "error": err,
        "latest": (
            {
                "ts": latest[1].get("ts"),
                "date": latest[1].get("date"),
                "kind": latest[1].get("kind"),
                "reason": latest[1].get("reason"),
                "counts": latest[1].get("counts"),
            }
            if latest
            else None
        ),
    }


def render(s: Dict[str, Any]) -> str:
    head = "RUN_HEALTH_ALERTS: %s n=%d bad=%d undated=%d since=%s path=%s" % (
        s["state"], s["n"], len(s["bad_lines"]), s["undated"], s["since"], s["path"],
    )
    lines = [head]
    if s.get("note"):
        lines.append("  note: " + str(s["note"]))
    if s["state"] == "SKIP":
        lines.append("  -> SKIP：非 Mimir 主机（home 目录不存在）——CI 上不假红")
    elif s["state"] == "NO_ALERTS_YET":
        lines.append("  -> 明示『从未越线』：台账未创建是合法的，不等于出声通路故障")
    if s["state"] == "MISSING":
        lines.append(
            "  -> 出声通路断了：台账文件不存在（run_health 从未越线，或被删）。"
            "此态 != 无告警。"
        )
    elif s["state"] == "UNREADABLE":
        lines.append("  -> 台账不可读：%s（权限/IO）——本轮读数不可信。" % s["error"])
    elif s["state"] == "PARSE_ERROR":
        lines.append(
            "  -> 坏行 %d 条（行号 %s）——已解析部分仍列出，但计数可能偏低。"
            % (len(s["bad_lines"]), s["bad_lines"][:5])
        )
    if s["state"] in ("ALERT", "PARSE_ERROR"):
        lat = s.get("latest") or {}
        if lat:
            lines.append(
                "  latest: ts=%s date=%s kind=%s reason=%s"
                % (lat.get("ts"), lat.get("date"), lat.get("kind"), lat.get("reason"))
            )
        if s["by_kind"]:
            lines.append(
                "  by_kind: "
                + " ".join("%s=%d" % (k, v) for k, v in sorted(s["by_kind"].items()))
            )
    if s["state"] == "NONE":
        lines.append("  -> 明示『无告警』（非静默）：台账在盘且窗口内 0 条")
    return "\n".join(lines)


def rc_for(state: str) -> int:
    return {
        "MISSING": RC_UNREADABLE,
        "UNREADABLE": RC_UNREADABLE,
        "PARSE_ERROR": RC_PARSE_ERROR,
        "ALERT": RC_ALERTS,
        "NONE": RC_NONE,
        "SKIP": RC_NONE,
        "NO_ALERTS_YET": RC_NONE,
    }[state]


def _home_of(p: Path) -> Path:
    """从台账路径反推 Mimir 家（<home>/data/ops/<file>）；推不出则回落 mimir_home()。"""
    try:
        return p.parents[2]
    except Exception:
        return mimir_home()


def _probe(path: Path, since: str = "all", home: Optional[Path] = None) -> Tuple[Dict[str, Any], int, str]:
    """一次读口调用（selftest / 受控触发用）。"""
    w = parse_window(since)
    recs, bad, err = read_alerts(path)
    kept, undated = select(recs, w)
    s = summarize(kept, bad, err, path=path, since=since, undated=undated)
    if s["state"] == "MISSING" and home is not None:
        sub, note = missing_diagnosis(home)
        s["state"], s["note"] = sub, note
    return s, rc_for(s["state"]), render(s)


def selftest() -> int:
    """三坏病例 + 三孪生对照（不联盘、不联网）。

    只证明「坏样本被拒」不算数 —— 必须同时证明「好样本不被误拦」。
    """
    import tempfile

    cases: List[Tuple[str, bool, str, str]] = []  # (label, good, want, got)

    def rec(label: str, want: str, got: str) -> None:
        cases.append((label, want == got, want, got))

    with tempfile.TemporaryDirectory(prefix="f2_alerts_selftest_") as td:
        d = Path(td)
        good = d / "good.jsonl"
        good.write_text(
            json.dumps({"ts": "2026-10-07T02:48:32", "date": "2026-10-07",
                        "kind": "max_turns", "reason": "max_turns=1>=1"}) + "\n",
            encoding="utf-8",
        )
        empty = d / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        corrupt = d / "corrupt.jsonl"
        corrupt.write_text(
            json.dumps({"ts": "2026-10-07T02:48:32", "kind": "max_turns"}) + "\n" + "{oops\n",
            encoding="utf-8",
        )
        missing = d / "missing.jsonl"

        # ① 坏：文件缺失 -> MISSING；孪生：空文件在盘 -> NONE（证明 MISSING 不是恒真）
        s, rc, out = _probe(missing)
        rec("坏1 缺失台账 -> MISSING/rc3", "MISSING:3", "%s:%d" % (s["state"], rc))
        s, rc, out = _probe(empty)
        rec("孪1 空台账 -> NONE/rc0", "NONE:0", "%s:%d" % (s["state"], rc))
        rec("孪1b 无告警必须明示（禁空白静默）", "yes", "yes" if out.strip() else "no")

        # ② 坏：坏行 -> PARSE_ERROR；孪生：同内容去掉坏行 -> ALERT（证明 PARSE 不是恒真）
        s, rc, out = _probe(corrupt)
        rec("坏2 坏行 -> PARSE_ERROR/rc4", "PARSE_ERROR:4", "%s:%d" % (s["state"], rc))
        s, rc, out = _probe(good)
        rec("孪2 好台账 -> ALERT/rc2", "ALERT:2", "%s:%d" % (s["state"], rc))

        # ③ 坏：窗口外 -> NONE；孪生：全量窗口 -> ALERT（证明窗口过滤真生效）
        s, rc, out = _probe(good, "1m")
        rec("坏3 窗口外 -> NONE/rc0", "NONE:0", "%s:%d" % (s["state"], rc))
        s, rc, out = _probe(good, "all")
        rec("孪3 全量窗 -> ALERT/rc2", "ALERT:2", "%s:%d" % (s["state"], rc))

        # ④ 缺失台账三分辨（防假红 + 防假绿）：SKIP / NO_ALERTS_YET / MISSING
        s, rc, out = _probe(missing, "all", home=d / "nohome")
        rec("坏4 非主机(无 home) -> SKIP/rc0", "SKIP:0", "%s:%d" % (s["state"], rc))
        h2 = d / "h2"
        (h2 / "data" / "ops").mkdir(parents=True)
        (h2 / "data" / "ops" / "run_health_state.json").write_text(
            json.dumps({"alerted": {}}), encoding="utf-8")
        s, rc, out = _probe(missing, "all", home=h2)
        rec("孪4a 从未越线 -> NO_ALERTS_YET/rc0", "NO_ALERTS_YET:0", "%s:%d" % (s["state"], rc))
        (h2 / "data" / "ops" / "run_health_state.json").write_text(
            json.dumps({"alerted": {"2026-10-07": {"max_turns": True}}}), encoding="utf-8")
        s, rc, out = _probe(missing, "all", home=h2)
        rec("坏5 已 fire 但台账缺 -> MISSING/rc3", "MISSING:3", "%s:%d" % (s["state"], rc))

    ok = True
    for label, good_, want, got in cases:
        ok = ok and good_
        print("[selftest] %s %s: 期望 %s / 实得 %s" % ("PASS" if good_ else "FAIL", label, want, got))
    print("[selftest] " + ("ALL PASS" if ok else "HAS FAILURE"))
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="run_health 告警台账读口（纯只读 · F2 第 8 单）")
    ap.add_argument("--since", default="all", help="窗口，如 24h / 90m / 7d（默认 all）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（stdout）；rc 语义不变")
    ap.add_argument("--selftest", action="store_true", help="跑合成坏病例/孪生对照（不联盘）")
    ap.add_argument("--path", default=None, help="覆盖台账路径（测试/受控触发用）")
    ap.add_argument("--gate", action="store_true",
                    help="闸门模式：只对『通路故障』(缺失/不可读/坏行) 非 0；有告警只打印不判死")
    ap.add_argument("--home", default=None, help="覆盖 Mimir 家（受控触发/自证用）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.home:
        # 显式 --home 优先于任何环境键（且**不走共用键 HERMES_HOME**）
        # 2026-10-07 第 20 单：旧版 --home 只影响诊断、不影响读路径 ⇒ 假红。
        os.environ["MIMIR_AETHER_HOME"] = str(Path(args.home).expanduser())
    window = parse_window(args.since)
    p = Path(args.path) if args.path else alert_path()
    home = Path(args.home) if args.home else _home_of(p)
    recs, bad, err = read_alerts(p)
    kept, undated = select(recs, window)
    s = summarize(kept, bad, err, path=p, since=args.since, undated=undated)
    if s["state"] == "MISSING":
        sub, note = missing_diagnosis(home)
        s["state"], s["note"] = sub, note
    rc = rc_for(s["state"])
    if args.gate and s["state"] == "ALERT":
        rc = RC_NONE  # gate 模式：告警要**被看见**（照常打印），但不因此判死出声通路
    if args.json:
        print(json.dumps(s, ensure_ascii=False, sort_keys=True))
    else:
        print(render(s))
    return rc


if __name__ == "__main__":
    sys.exit(main())
