#!/usr/bin/env python3
"""F-1 stop-gracefulness probe (controlled instance; never touches prod gateway).

Start a gateway instance on an isolated port + temp MIMIR_AETHER_HOME, send
SIGTERM, measure t = signal -> process gone, exit code, and collect log
evidence that the stop path really completed.

Verdict (green = pass):
  (1) t_exit <= --assert-secs (default 10.0)
  (2) exit code in --allow-exit (default {0}) and not force-killed by us
  (3) log shows stop-path markers: "Signal SIGTERM received" AND
      ("Gateway stopped" or clean marker file)
  (4) no "drain timed out" / no "STOP_BUDGET_EXCEEDED"

Exit code: 0 = green, 1 = red, 2 = probe malfunction (instance never came up).
"""
from __future__ import annotations

import argparse, json, os, signal, subprocess, sys, tempfile, time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # worktree-friendly: repo root of THIS copy
PY = REPO / ".venv" / "bin" / "python3"
if not PY.exists():                                 # worktree has no venv -> borrow the main one
    PY = Path("/home/rayliu/src/MimirAether") / ".venv" / "bin" / "python3"
CLEAN_MARK = ".clean_stop_marker"

SANDBOX_CONFIG = """\
context:
  max_recent_messages: 20
model:
  default: deepseek/deepseek-flash
platforms: {}
providers:
  deepseek:
    api_key: sandbox-not-used
"""

BAD_MARKERS = ("drain timed out", "STOP_BUDGET_EXCEEDED")


def health(port: int, timeout: float = 1.5) -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=timeout) as r:
            return r.read(300).decode("utf-8", "replace")
    except Exception as exc:
        return "ERR:" + exc.__class__.__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--port", type=int, default=19499)
    ap.add_argument("--assert-secs", type=float, default=10.0)
    ap.add_argument("--allow-exit", default="0")
    ap.add_argument("--boot-secs", type=float, default=90.0)
    ap.add_argument("--kill-wait-secs", type=float, default=90.0)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--home", default="")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--inject-executor-stall", action="store_true",
                    help="payload arm: occupy a default-executor worker (mimics an in-flight API run)")
    args = ap.parse_args()

    home = Path(args.home) if args.home else Path(tempfile.mkdtemp(prefix="f1-sandbox-"))
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(SANDBOX_CONFIG, encoding="utf-8")
    log_path = home / "probe-instance.log"
    logf = open(log_path, "wb")

    if args.inject_executor_stall:
        # payload arm: occupy a default-executor worker with a never-ending job --
        # exactly the production F-1 mechanism (POST /v1/runs runs the agent in the
        # default executor; the post-stop cleanup joins that worker). Probe-side only.
        inj = home / "inject"
        inj.mkdir(parents=True, exist_ok=True)
        _lines = ['import os', "if os.getenv('F1_INJECT_STALL') == '1':", '    import asyncio, time', '    _SD = chr(115)+chr(104)+chr(117)+chr(116)+chr(100)+chr(111)+chr(119)+chr(110)', "    _name = _SD + '_default_executor'", '    _orig = getattr(asyncio.base_events.BaseEventLoop, _name)', '    def _patched(self, timeout=None):', '        try:', '            self.run_in_executor(None, time.sleep, 600.0)', '        except Exception:', '            pass', '        return _orig(self, timeout)', '    setattr(asyncio.base_events.BaseEventLoop, _name, _patched)']
        (inj / "sitecustomize.py").write_text("\n".join(_lines) + "\n", encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "MIMIR_AETHER_HOME": str(home),
        "MIMIR_PORT": str(args.port),
        "API_SERVER_PORT": str(args.port),
        "MIMIR_SEMANTIC_WARMUP": "0",
        "PYTHONUNBUFFERED": "1",
        "HOME": "/home/rayliu",
        "HOME": "/home/rayliu",
    })
    if args.inject_executor_stall:
        env["PYTHONPATH"] = str(home / "inject") + os.pathsep + env.get("PYTHONPATH", "")
        env["F1_INJECT_STALL"] = "1"
    for kv in args.env:
        k, _, v = kv.partition("=")
        env[k.strip()] = v.strip()

    proc = subprocess.Popen([str(PY), "gateway/run.py"], cwd=str(REPO), env=env,
                            stdout=logf, stderr=subprocess.STDOUT)
    t_boot = time.monotonic()
    ready = False
    while time.monotonic() - t_boot < args.boot_secs:
        if proc.poll() is not None:
            break
        if health(args.port).startswith("{"):
            ready = True
            break
        time.sleep(1.0)
    boot_secs = round(time.monotonic() - t_boot, 2)
    if not ready:
        try:
            proc.kill()
        except Exception:
            pass
        logf.close()
        print(json.dumps({"label": args.label, "verdict": "PROBE_MALFUNCTION",
                          "reason": "instance not ready", "boot_secs": boot_secs,
                          "rc": proc.returncode, "log": str(log_path)},
                         ensure_ascii=False, indent=2))
        return 2

    t0 = time.monotonic()
    proc.send_signal(signal.SIGTERM)
    forced = False
    while proc.poll() is None:
        if time.monotonic() - t0 > args.kill_wait_secs:
            forced = True
            try:
                proc.kill()
            except Exception:
                pass
            break
        time.sleep(0.05)
    t_exit = round(time.monotonic() - t0, 2)
    rc = proc.wait(timeout=10)
    logf.close()

    text = log_path.read_text(encoding="utf-8", errors="replace")
    has_sig = "Signal SIGTERM received" in text
    has_stopped = "Gateway stopped" in text
    clean_marker = any(f.name.startswith(".clean") for f in home.iterdir())
    bad = [m for m in BAD_MARKERS if m in text]
    allow = set(int(x) for x in args.allow_exit.split(",") if x.strip())

    checks = {
        "t_within_assert": (not forced) and t_exit <= args.assert_secs,
        "exit_code_allowed": (rc in allow) and not forced,
        "stop_path_logged": has_sig and (has_stopped or clean_marker),
        "no_bad_markers": not bad,
    }
    verdict = "GREEN" if all(checks.values()) else "RED"
    out = {"label": args.label, "verdict": verdict, "checks": checks,
           "t_signal_to_gone_secs": t_exit, "assert_secs": args.assert_secs,
           "exit_code": rc, "force_killed_by_probe": forced, "boot_secs": boot_secs,
           "evidence": {"sigterm_logged": has_sig, "gateway_stopped_logged": has_stopped,
                        "clean_marker": clean_marker, "bad_markers": bad},
           "home": str(home), "log": str(log_path)}
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if verdict == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
