#!/usr/bin/env python3
"""
pi_crew_bridge.py — 沙盒桥接层（试点 1：论文精读自动 team）

基于 pi-crew v0.9.56 源码精读（2026-08-01）：
- src/config/defaults.ts:169  DEFAULT_BROKER = { enabled: true }  <- broker 默认开启
- src/config/defaults.ts:187  PI_CREW_BROKER=0 env 覆盖 config=true（最强关闭方式）
- src/extension/team-tool/run.ts:254  executeWorkers 默认 true（每 task 独立 Pi 进程）
- teams/research.team.md / parallel-research.team.md 确认存在（explorer->analyst->writer）

安全边界（讨论室 Q2 共识）：
1. 强制 PI_CREW_BROKER=0（OpenClaw 补丁 3 — 缺这条 = 试点不可接受）
2. 只允许 research / parallel-research team（Hermes 补丁 1）
3. 工作目录锁死在 ~/src/MimirAether/（OpenClaw 补丁 1 沙盒路径）
4. 审计日志：每次调用写 ~/.mimiraether/logs/pi-crew-audit-{DATE}.log（OpenClaw 补丁 2）
5. 单 tool call 模式，不用 exec heredoc/pipe（Loki 补丁 4）

异步模式（方案 A · 2026-08-02 拍板）：
- pi -p 只负责发起 run（child-process 模式，run 是独立子进程）
- bridge 轮询 .crew/state/runs/<run_id>/manifest.json 直到 status==completed/failed
- start_new_session=True 分离进程组：bridge 超时返回不杀 run 子进程
- 收集 .crew/artifacts/<run_id>/ 产物到输出
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 沙盒常量 ──────────────────────────────────────────────
ALLOWED_TEAMS = {"research", "parallel-research"}
WORKSPACE_ROOT = Path(os.environ.get("MIMIR_AETHER_HOME", Path.home() / ".mimiraether")).resolve()
# 工作目录锁死：repo 根（pi-crew 只在这里跑）
CREW_CWD = Path("/home/rayliu/src/MimirAether")
# 禁写路径（OpenClaw 补丁 1）—— 任何输出路径命中这些前缀即拒绝
FORBIDDEN_PREFIXES = [
    "/home/rayliu/.openclaw/",
    "/home/rayliu/wiki/concepts/",
    "/home/rayliu/wiki/discussions/",
    "/home/rayliu/.mimiraether/cron/",
    "/home/rayliu/.mimiraether/SOUL.md",
    "/home/rayliu/.mimiraether/AGENTS.md",
    "/home/rayliu/.mimiraether/MEMORY.md",
]
AUDIT_DIR = WORKSPACE_ROOT / "logs"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# pi CLI 路径（此前验证过）
PI_BIN = os.environ.get("PI_BIN", "/home/rayliu/.bun/bin/pi")

# pi-crew run 状态根（child-process 模式产物）
RUNS_ROOT = CREW_CWD / ".crew" / "state" / "runs"
ARTIFACTS_ROOT = CREW_CWD / ".crew" / "artifacts"

# 轮询参数
POLL_INTERVAL = 5          # 秒
SPAWN_TIMEOUT = 120        # 等 run 目录出现的最长时间
DEFAULT_TIMEOUT = 600      # 方案 A：run 完成等待上限


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _audit_log(entry: dict) -> None:
    """OpenClaw 补丁 2：文件操作审计。没有审计日志 = 该次 run 算 fail。"""
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = AUDIT_DIR / f"pi-crew-audit-{date}.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _assert_safe(team: str, goal: str) -> None:
    """沙盒校验：team 白名单 + goal 禁写路径扫描。"""
    if team not in ALLOWED_TEAMS:
        raise ValueError(f"Team '{team}' not in allowlist: {sorted(ALLOWED_TEAMS)}")
    low = goal.lower()
    for p in FORBIDDEN_PREFIXES:
        if p.lower() in low:
            raise ValueError(f"Goal references forbidden path prefix: {p}")


def _build_prompt(team: str, goal: str) -> str:
    """pi-crew 是 pi extension（team tool），不是 CLI 子命令。
    正确调用 = pi -p 非交互模式，提示 pi 通过 team tool 执行 action=run。"""
    return (
        f"Use the team tool with action=run to execute the research team workflow.\n"
        f"team: {team}\n"
        f"goal: {goal}\n"
        f"Call the team tool exactly once with {{\"action\":\"run\",\"team\":\"{team}\",\"goal\":\"{goal}\"}}. "
        f"Wait for the run to complete, then report the run id and a concise summary."
    )


def _load_env() -> dict:
    """注入 MimirAether .env（DEEPSEEK_API_KEY 等）—— pi 子进程需要它。
    对齐 subagent_bridge._load_env() 模式（2026-08-02 实测 pi 读不到 key）。"""
    env = os.environ.copy()
    mimir_env = Path.home() / ".mimiraether" / ".env"
    if mimir_env.is_file():
        with open(mimir_env) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    # broker 必须 OFF（默认 true！）+ 双保险清空 socket 凭证
    env["PI_CREW_BROKER"] = "0"
    env["PI_CREW_BROKER_SOCKET"] = ""
    env["PI_CREW_BROKER_TOKEN"] = ""
    env["PI_CREW_BROKER_RUN_ID"] = ""
    env["PI_CREW_BROKER_TASK_ID"] = ""
    return env


def _existing_run_names() -> set:
    if not RUNS_ROOT.is_dir():
        return set()
    return {p.name for p in RUNS_ROOT.iterdir() if p.is_dir()}


def _read_manifest(run_dir: Path) -> dict:
    mf = run_dir / "manifest.json"
    if not mf.is_file():
        return {}
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _wait_run(run_dir: Path, timeout: int) -> dict:
    """轮询 manifest.json status 直到 completed/failed 或超时。
    不杀任何进程——run 是 child-process，独立于 bridge 生命周期。"""
    t0 = time.time()
    last_status = "unknown"
    while time.time() - t0 < timeout:
        m = _read_manifest(run_dir)
        status = m.get("status", "unknown")
        if status != last_status:
            last_status = status
        if status in ("completed", "succeeded", "done"):
            return {"status": "completed", "manifest": m, "waited_s": round(time.time() - t0, 1)}
        if status in ("failed", "error", "cancelled", "aborted"):
            return {"status": "failed", "manifest": m, "waited_s": round(time.time() - t0, 1)}
        time.sleep(POLL_INTERVAL)
    return {"status": "timeout", "manifest": _read_manifest(run_dir), "waited_s": round(time.time() - t0, 1)}


def _collect_artifacts(run_id: str) -> list:
    """收集 .crew/artifacts/<run_id>/ 下的产物文件。"""
    art_dir = ARTIFACTS_ROOT / run_id
    out = []
    if art_dir.is_dir():
        for f in sorted(art_dir.rglob("*")):
            if f.is_file():
                out.append({"path": str(f), "size": f.stat().st_size})
    return out


def run_crew(
    team: str = "research",
    goal: str = "",
    workflow: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    pi_bin: str | None = None,
) -> dict:
    """
    执行一次 pi-crew run（research / parallel-research）——异步模式。

    流程：
      1. pi -p 非交互启动（start_new_session=True 分离进程组）
      2. 等 .crew/state/runs/ 出现新 run 目录（最长 SPAWN_TIMEOUT）
      3. 轮询 manifest.json status 直到 completed/failed/超时（不杀进程）
      4. 收集 artifacts
    返回 {run_id, status, output, artifacts, audit_log, duration_s}
    """
    t0 = time.time()
    _assert_safe(team, goal)
    bin_path = pi_bin or PI_BIN
    prompt = _build_prompt(team, goal)
    env = _load_env()

    # 记录启动前已有的 run 目录（用于识别本次新 run）
    runs_before = _existing_run_names()

    # stdout/stderr 用临时文件重定向（不用 PIPE——pi 持续输出会写满 64KB pipe
    # buffer 导致进程写阻塞、不创建 run；文件不阻塞，轮询期间可读尾部）
    out_fd, out_path = tempfile.mkstemp(prefix="pi-bridge-", suffix=".out", text=True)
    err_fd, err_path = tempfile.mkstemp(prefix="pi-bridge-", suffix=".err", text=True)
    os.close(out_fd)
    os.close(err_fd)

    try:
        proc = subprocess.Popen(
            [bin_path, "-p", prompt],
            cwd=str(CREW_CWD),
            env=env,
            stdout=open(out_path, "w", encoding="utf-8"),
            stderr=open(err_path, "w", encoding="utf-8"),
            text=True,
            start_new_session=True,  # 方案 A：分离进程组，超时不杀子进程
        )
    except Exception as e:
        entry = {
            "ts": _now(), "team": team, "workflow": workflow, "goal": goal[:200],
            "ok": False, "run_id": None, "duration_s": round(time.time() - t0, 1),
            "exit_code": None, "pid": os.getpid(), "error": str(e),
        }
        _audit_log(entry)
        return {"run_id": None, "status": "failed", "output": "", "stderr": str(e),
                "audit_log": str(AUDIT_DIR / f"pi-crew-audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"),
                "duration_s": round(time.time() - t0, 1), "env_guards": {"PI_CREW_BROKER": "0 (forced)"}}

    # 阶段 1：等待新 run 目录出现（pi -p 发起 run）
    run_dir = None
    s0 = time.time()
    while time.time() - s0 < SPAWN_TIMEOUT:
        for p in RUNS_ROOT.iterdir() if RUNS_ROOT.is_dir() else []:
            if p.is_dir() and p.name not in runs_before:
                run_dir = p
                break
        if run_dir is not None:
            break
        if proc.poll() is not None:
            # pi -p 提前退出，未创建 run —— 读输出诊断
            try:
                stdout = open(out_path, encoding="utf-8", errors="replace").read()
                stderr = open(err_path, encoding="utf-8", errors="replace").read()
            except Exception:
                stdout, stderr = "", ""
            entry = {
                "ts": _now(), "team": team, "workflow": workflow, "goal": goal[:200],
                "ok": False, "run_id": None, "duration_s": round(time.time() - t0, 1),
                "exit_code": proc.returncode, "pid": os.getpid(),
                "stderr_tail": stderr[-500:],
            }
            _audit_log(entry)
            return {"run_id": None, "status": "failed", "output": stdout[-2000:], "stderr": stderr[-2000:],
                    "audit_log": str(AUDIT_DIR / f"pi-crew-audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"),
                    "duration_s": round(time.time() - t0, 1), "env_guards": {"PI_CREW_BROKER": "0 (forced)"}}
        time.sleep(2)

    if run_dir is None:
        # SPAWN_TIMEOUT 内未创建 run
        entry = {
            "ts": _now(), "team": team, "workflow": workflow, "goal": goal[:200],
            "ok": False, "run_id": None, "duration_s": round(time.time() - t0, 1),
            "exit_code": None, "pid": os.getpid(), "error": f"no run created within {SPAWN_TIMEOUT}s",
        }
        _audit_log(entry)
        return {"run_id": None, "status": "failed", "output": "", "stderr": f"no run created within {SPAWN_TIMEOUT}s",
                "audit_log": str(AUDIT_DIR / f"pi-crew-audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"),
                "duration_s": round(time.time() - t0, 1), "env_guards": {"PI_CREW_BROKER": "0 (forced)"}}

    # 阶段 2：run 已创建，轮询直到 completed/failed/超时（不杀进程）
    run_id = run_dir.name
    elapsed_spawn = time.time() - s0
    wait_result = _wait_run(run_dir, timeout=max(30, timeout - elapsed_spawn))
    artifacts = _collect_artifacts(run_id)
    ok = wait_result["status"] == "completed"

    duration = round(time.time() - t0, 1)
    entry = {
        "ts": _now(), "team": team, "workflow": workflow, "goal": goal[:200],
        "ok": ok, "run_id": run_id, "duration_s": duration,
        "exit_code": proc.poll(), "pid": os.getpid(),
        "run_status": wait_result["status"], "artifacts": len(artifacts),
    }
    _audit_log(entry)

    # 尝试收割 pi -p 会话（run 完成后它通常自己退出；不强制 kill）
    try:
        if proc.poll() is None:
            proc.wait(timeout=10)
    except Exception:
        pass  # 留给系统回收，不杀

    output_parts = [f"run_id={run_id}", f"status={wait_result['status']}", f"waited_s={wait_result['waited_s']}"]
    if artifacts:
        output_parts.append(f"artifacts={len(artifacts)}")
        for a in artifacts[:20]:
            output_parts.append(f"  {a['path']} ({a['size']}B)")
    if wait_result["status"] == "failed":
        m = wait_result.get("manifest", {})
        output_parts.append(f"manifest_summary={str(m.get('summary', ''))[:200]}")

    return {
        "run_id": run_id,
        "status": "ok" if ok else "failed",
        "output": "\n".join(output_parts),
        "stderr": "",
        "artifacts": artifacts,
        "audit_log": str(AUDIT_DIR / f"pi-crew-audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"),
        "duration_s": duration,
        "env_guards": {"PI_CREW_BROKER": "0 (forced)"},
    }


def main() -> None:
    """CLI 入口：python pi_crew_bridge.py --team research --goal "..." """
    import argparse

    p = argparse.ArgumentParser(description="pi-crew 沙盒桥接层（异步模式）")
    p.add_argument("--team", default="research", choices=sorted(ALLOWED_TEAMS))
    p.add_argument("--goal", required=True, help="团队目标（自动扫描禁写路径）")
    p.add_argument("--workflow", default=None)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = p.parse_args()

    result = run_crew(team=args.team, goal=args.goal, workflow=args.workflow, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
