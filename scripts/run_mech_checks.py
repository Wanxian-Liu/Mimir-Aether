#!/usr/bin/env python3
"""run_mech_checks.py — RS19 P0 统一机械检查 runner（触发 + 解析 + 记录 + 告警）。

设计真源：`~/wiki/discussions/2026-09-14-提案-RS19统一机械检查清单与失败告警.md`
（§31 Hermes 复核通过，Q1-Q5 全裁；P0 只注册 owner=mimir 的项）。

契约（与方案卡 §2.2 一致）
  1. 只读优先：`readonly: false` 的项默认跳过（--allow-write 才跑）；
  2. 不吞异常：四态严格区分
       PASS    = 检查器判定合格
       FAIL    = 检查器判定不合格
       ERROR   = 检查器自己坏了（不可执行 / 超时 / 输出无法解析 / 判据自相矛盾）
       SKIPPED = 因 readonly 守卫未执行（不得被读成 PASS）
  3. 单项隔离：每项独立进程 + 独立超时（超时杀进程组，不留孤儿）；
  4. 落盘：`last_run.json`（当前状态）+ `history.jsonl`（append-only，一项一行）；
  5. 退出码：0 = 全 PASS；1 = 有 FAIL；2 = 有 ERROR/SKIPPED；3 = 心跳过期；
  6. 无业务副作用：唯一写入 = 注册表 outputs 两处 + 告警日志。

用法
  python3 scripts/run_mech_checks.py
  python3 scripts/run_mech_checks.py --only fts_idempotency
  python3 scripts/run_mech_checks.py --no-notify
  python3 scripts/run_mech_checks.py --heartbeat
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

def _resolve_home_default() -> Path:
    """Resolve the runtime data root without the ``$HOME`` double-nesting trap.

    ``$HOME`` may already point at the runtime root (sandboxes set
    ``HOME=~/.mimiraether``); appending ``.mimiraether`` again yields
    ``<root>/.mimiraether`` and every default path silently misses
    (2026-09-26: registry default became non-existent -> FileNotFoundError).
    """
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "MIMIR_HOME"):
        v = os.getenv(key, "").strip()
        if v:
            return Path(v).expanduser()
    home = Path.home()
    if home.name == ".mimiraether":
        return home
    return home / ".mimiraether"


HOME_DEFAULT = _resolve_home_default()
REGISTRY_DEFAULT = HOME_DEFAULT / "data" / "ops" / "mech_checks.json"
STDOUT_TAIL_CHARS = 800
STATUSES = ("PASS", "FAIL", "ERROR", "SKIPPED")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expand(text: str, subs: dict) -> str:
    out = str(text)
    for key, val in subs.items():
        out = out.replace(key, val)
    return out


def _run_command(cmd: str, cwd: str, timeout_s: int, env: dict) -> dict:
    """跑单项。status_hint=None 表示交判据解析；ERROR 表示执行层已判定故障。"""
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            shlex.split(cmd),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except (FileNotFoundError, PermissionError, OSError, ValueError) as exc:
        return {
            "status_hint": "ERROR",
            "exit_code": None,
            "stdout": "",
            "elapsed_s": round(time.monotonic() - started, 3),
            "error": f"exec_failed: {type(exc).__name__}: {exc}",
        }
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        out, _ = proc.communicate()
        return {
            "status_hint": "ERROR",
            "exit_code": None,
            "stdout": out or "",
            "elapsed_s": round(time.monotonic() - started, 3),
            "error": f"timeout after {timeout_s}s",
        }
    return {
        "status_hint": None,
        "exit_code": proc.returncode,
        "stdout": out or "",
        "elapsed_s": round(time.monotonic() - started, 3),
        "error": "",
    }


def _verdict_of(stdout: str, pattern: str):
    if not pattern:
        return None
    match = re.search(pattern, stdout, re.MULTILINE)
    return match.group(1).upper() if match else None


def _status_for(result: dict, item: dict):
    """返回 (status, reason)。判据冲突一律 ERROR，不得读成 PASS。"""
    if result["status_hint"] == "ERROR":
        return "ERROR", result["error"]
    exit_code = result["exit_code"]
    exit_ok = item.get("exit_ok", [0])
    if item.get("verdict_parse"):
        verdict = _verdict_of(result["stdout"], item["verdict_parse"])
        if verdict is None:
            return "ERROR", "unparseable: verdict line not found in stdout"
        if verdict == "FAIL":
            return "FAIL", "verdict=FAIL"
        if exit_code not in exit_ok:
            return "ERROR", f"verdict=PASS but exit_code={exit_code} not in {exit_ok}"
        return "PASS", "verdict=PASS"
    if exit_code in exit_ok:
        return "PASS", f"exit_code={exit_code}"
    return "FAIL", f"exit_code={exit_code} not in {exit_ok}"


def _prev_statuses(last_run: dict) -> dict:
    return {it.get("id"): it.get("status") for it in last_run.get("items", [])}


def _notify(cmd, timeout_s: int = 30):
    """告警通道坏不得拖死 runner ⇒ 绝不抛。"""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()[:200]
    return True, "sent"


def _alert_line(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{_now_iso()} {text}\n")


def _feishu_cmd(chat_id: str, text: str, dry_run: bool):
    cmd = ["lark-cli", "im", "+messages-send", "--chat-id", chat_id, "--text", text]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def _cfg(args):
    registry_path = Path(args.registry).expanduser()
    registry = _load_json(registry_path)
    subs = {k: str(Path(v).expanduser()) for k, v in registry.get("placeholders", {}).items()}
    outputs = registry.get("outputs", {})
    alerts_cfg = registry.get("alerts", {})
    return {
        "path": registry_path,
        "registry": registry,
        "subs": subs,
        "alerts": alerts_cfg,
        "alert_log": Path(_expand(alerts_cfg.get("log", "{home}/logs/mech_checks_alert.log"), subs)),
        "last_run": Path(_expand(outputs.get("last_run", "{home}/data/ops/mech_checks/last_run.json"), subs)),
        "history": Path(_expand(outputs.get("history", "{home}/data/ops/mech_checks/history.jsonl"), subs)),
    }


def run_checks(args) -> int:
    cfg = _cfg(args)
    registry, subs = cfg["registry"], cfg["subs"]
    defaults = registry.get("defaults", {})
    prev = _prev_statuses(_load_json(cfg["last_run"])) if cfg["last_run"].exists() else {}
    env = dict(os.environ)
    # Both spellings are read across the repo checkers; keep them in sync.
    env.setdefault("MIMIR_HOME", str(HOME_DEFAULT))
    env.setdefault("MIMIR_AETHER_HOME", str(HOME_DEFAULT))

    run_id = f"mech-{int(time.time())}"
    started_at = _now_iso()
    items_out = []
    alerts = []

    for raw in registry.get("items", []):
        item = {**defaults, **raw}
        item_id = item.get("id", "?")
        if args.only and item_id not in args.only:
            continue
        if not item.get("readonly", True) and not args.allow_write:
            items_out.append({
                "id": item_id, "owner": item.get("owner"), "status": "SKIPPED",
                "severity": item.get("severity"), "exit_code": None, "elapsed_s": 0.0,
                "stdout_tail": "", "reason": "readonly=false 且未传 --allow-write",
            })
            continue
        cmd = _expand(item.get("cmd", ""), subs)
        result = _run_command(cmd, subs.get("{repo}", str(Path.cwd())),
                              int(item.get("timeout_s", 60)), env)
        status, reason = _status_for(result, item)
        items_out.append({
            "id": item_id, "owner": item.get("owner"), "status": status,
            "severity": item.get("severity"), "exit_code": result["exit_code"],
            "elapsed_s": result["elapsed_s"],
            "stdout_tail": (result["stdout"] or "")[-STDOUT_TAIL_CHARS:],
            "reason": reason, "cmd": cmd,
        })
        prev_status = prev.get(item_id)
        # Q1 裁决：状态变化才告警（FAIL→FAIL 不重复轰炸；首跑 prev=None 视为变化）
        if status in ("FAIL", "ERROR") and prev_status != status and item.get("severity") == "high":
            label = "检查器故障" if status == "ERROR" else "被检对象不合格"
            alerts.append(f"[{status}] {item_id} ({label}) :: {reason}")
        elif status == "PASS" and prev_status in ("FAIL", "ERROR"):
            alerts.append(f"[RECOVERED] {item_id} :: {prev_status} -> PASS")

    finished_at = _now_iso()
    summary = {s: sum(1 for it in items_out if it["status"] == s) for s in STATUSES}
    payload = {
        "run_id": run_id, "started_at": started_at, "finished_at": finished_at,
        "host": socket.gethostname(), "pid": os.getpid(),
        "registry": str(cfg["path"]), "registry_sha256": _sha256(cfg["path"]),
        "gate_version": "rs19.p0.v1", "items": items_out, "summary": summary,
    }
    cfg["last_run"].parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg["last_run"].with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(cfg["last_run"])

    with cfg["history"].open("a", encoding="utf-8") as fh:
        for it in items_out:
            fh.write(json.dumps({
                "ts": finished_at, "run_id": run_id, "id": it["id"], "owner": it["owner"],
                "status": it["status"], "severity": it["severity"],
                "exit_code": it["exit_code"], "elapsed_s": it["elapsed_s"],
                "reason": it["reason"], "gate_version": payload["gate_version"],
            }, ensure_ascii=False) + "\n")

    for line in alerts:
        _alert_line(cfg["alert_log"], line)
    if alerts and not args.no_notify:
        text = "【RS19 机械检查】状态变化\n" + "\n".join(f"· {line}" for line in alerts)
        ok, info = _notify(_feishu_cmd(cfg["alerts"].get("chat_id", ""), text, args.notify_dry_run))
        _alert_line(cfg["alert_log"], f"[NOTIFY:{'ok' if ok else 'failed'}] {info}")

    verdict = "PASS" if not any(summary[k] for k in ("FAIL", "ERROR", "SKIPPED")) else "FAIL"
    print(f"VERDICT: {verdict}")
    print("items: " + " ".join(f"{it['id']}={it['status']}" for it in items_out))
    print("summary: " + " ".join(f"{k}={v}" for k, v in summary.items()))
    print(f"last_run: {cfg['last_run']}")
    if alerts:
        print("alerts:\n" + "\n".join(f"  {line}" for line in alerts))
    if summary["ERROR"] or summary["SKIPPED"]:
        return 2
    if summary["FAIL"]:
        return 1
    return 0


def check_heartbeat(args) -> int:
    """now - mtime(last_run) > 2 x min(interval_min) ⇒ 告警（退出 3）。"""
    cfg = _cfg(args)
    intervals = [int({**cfg["registry"].get("defaults", {}), **it}.get("interval_min", 360))
                 for it in cfg["registry"].get("items", [])]
    threshold_min = 2 * min(intervals) if intervals else 0
    if not cfg["last_run"].exists():
        _alert_line(cfg["alert_log"], f"[HEARTBEAT-EXPIRED] last_run.json 不存在（{cfg['last_run']}）")
        print(f"HEARTBEAT: EXPIRED (no last_run.json) threshold={threshold_min}min")
        return 3
    last = _load_json(cfg["last_run"])
    age_min = (time.time() - cfg["last_run"].stat().st_mtime) / 60.0
    if age_min > threshold_min:
        msg = (f"[HEARTBEAT-EXPIRED] last_run 距今 {age_min:.1f}min > {threshold_min}min"
               f"（run_id={last.get('run_id')} started_at={last.get('started_at')}）")
        _alert_line(cfg["alert_log"], msg)
        if not args.no_notify:
            ok, info = _notify(_feishu_cmd(cfg["alerts"].get("chat_id", ""),
                                           f"【RS19 心跳】{msg}", args.notify_dry_run))
            _alert_line(cfg["alert_log"], f"[NOTIFY:{'ok' if ok else 'failed'}] {info}")
        print(f"HEARTBEAT: EXPIRED age={age_min:.1f}min threshold={threshold_min}min")
        return 3
    print(f"HEARTBEAT: OK age={age_min:.1f}min threshold={threshold_min}min")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=str(REGISTRY_DEFAULT))
    parser.add_argument("--only", action="append", default=[], help="只跑指定 id（可重复）")
    parser.add_argument("--heartbeat", action="store_true", help="只做心跳判据检查")
    parser.add_argument("--no-notify", action="store_true", help="只写告警日志，不发飞书")
    parser.add_argument("--notify-dry-run", action="store_true", help="飞书发送走 --dry-run")
    parser.add_argument("--allow-write", action="store_true", help="允许跑 readonly=false 的项")
    args = parser.parse_args(argv)
    if args.heartbeat:
        return check_heartbeat(args)
    return run_checks(args)


if __name__ == "__main__":
    sys.exit(main())
