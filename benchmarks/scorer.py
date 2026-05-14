#!/usr/bin/env python3
"""
MimirAether Agent Benchmark Scorer — 外部判定器

原则: 不看 Agent 自述，只检查文件系统 / git / 进程 等客观证据。
每个任务的 score.py 返回:
  {"score": float, "max": float, "details": [...], "evidence": {...}}
"""

import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

BENCHMARK_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = BENCHMARK_ROOT / "results"


class TaskResult:
    """单个任务结果"""
    def __init__(self, task_id: str, agent_name: str):
        self.task_id = task_id
        self.agent_name = agent_name
        self.score = 0.0
        self.max_score = 0.0
        self.details: List[str] = []
        self.evidence: Dict[str, Any] = {}
        self.raw_output: str = ""

    def add_pass(self, description: str, points: float, evidence: Any = None):
        self.score += points
        self.max_score += points
        self.details.append(f"✅ {description}")
        if evidence:
            self.evidence[description] = evidence

    def add_fail(self, description: str, points: float, reason: str = "", evidence: Any = None):
        self.max_score += points
        self.details.append(f"❌ {description}" + (f" — {reason}" if reason else ""))
        if evidence is not None:
            self.evidence[description] = evidence

    def to_dict(self) -> dict:
        pct = round(100 * self.score / self.max_score, 1) if self.max_score > 0 else 0
        return {
            "task_id": self.task_id,
            "agent": self.agent_name,
            "score": self.score,
            "max": self.max_score,
            "percentage": pct,
            "details": self.details,
            "evidence": self.evidence,
        }


def run_shell(cmd: str, cwd: str = None, timeout: int = 30) -> subprocess.CompletedProcess:
    """运行 shell 命令，返回 CompletedProcess"""
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd, timeout=timeout
    )


def check_file_exists(path: str) -> bool:
    return os.path.exists(path)

def check_file_contains(path: str, pattern: str) -> bool:
    """检查文件内容是否包含 pattern"""
    if not os.path.exists(path):
        return False
    with open(path, 'r') as f:
        return pattern in f.read()

def check_git_commit(dirpath: str, message_pattern: str = None) -> bool:
    """检查是否有 git commit，可选检查 commit message"""
    try:
        result = run_shell("git log --oneline -1", cwd=dirpath)
        if result.returncode != 0:
            return False
        if message_pattern and message_pattern not in result.stdout:
            return False
        return True
    except:
        return False

def check_git_init(dirpath: str) -> bool:
    return os.path.isdir(os.path.join(dirpath, ".git"))

def check_json_valid(path: str) -> bool:
    try:
        with open(path) as f:
            json.load(f)
        return True
    except:
        return False

def check_command_success(cmd: str, cwd: str = None) -> bool:
    result = run_shell(cmd, cwd=cwd)
    return result.returncode == 0


def print_summary(results: List[TaskResult], agent_name: str):
    """打印汇总报告"""
    dims = {
        "tool_orch": {"weight": 0.25, "tasks": [], "name": "工具编排"},
        "codegen": {"weight": 0.20, "tasks": [], "name": "代码生成"},
        "error_recovery": {"weight": 0.20, "tasks": [], "name": "错误恢复"},
        "memory": {"weight": 0.20, "tasks": [], "name": "记忆持久"},
        "planning": {"weight": 0.15, "tasks": [], "name": "规划深度"},
    }

    for r in results:
        for prefix in dims:
            if r.task_id.startswith(prefix):
                dims[prefix]["tasks"].append(r)

    total_weighted = 0.0
    lines = []
    lines.append("=" * 60)
    lines.append(f"  🏟️  Agent Benchmark Report: {agent_name}")
    lines.append(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)

    for prefix, info in dims.items():
        tasks = info["tasks"]
        if not tasks:
            lines.append(f"\n  {info['name']} ({info['weight']*100:.0f}%) — 无数据")
            continue
        dim_score = sum(t.score for t in tasks)
        dim_max = sum(t.max_score for t in tasks)
        dim_pct = round(100 * dim_score / dim_max, 1) if dim_max > 0 else 0
        weighted = dim_pct * info["weight"]
        total_weighted += weighted
        lines.append(f"\n  {info['name']} ({info['weight']*100:.0f}%): {dim_pct}% → 加权 {weighted:.1f}")
        for t in tasks:
            tpct = round(100 * t.score / t.max_score, 1) if t.max_score > 0 else 0
            lines.append(f"    {t.task_id}: {tpct}%")
            for d in t.details:
                lines.append(f"      {d}")

    lines.append(f"\n  {'─'*50}")
    lines.append(f"  📊 加权总分: {total_weighted:.1f}/100")
    lines.append("=" * 60)

    return "\n".join(lines)


# ============================================================
# Main entry — 跑所有任务
# ============================================================
if __name__ == "__main__":
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    workdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/benchmark-sandbox"

    all_results = []

    # 遍历所有 task_* 目录，运行 score.py
    tasks_dir = BENCHMARK_ROOT / "tasks"
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        score_script = task_dir / "score.py"
        if not score_script.exists():
            continue

        # task_01_tool_orch → "tool_orch"
        raw_id = task_dir.name.replace("task_", "")
        # strip leading digits and underscore
        task_id = raw_id
        for prefix in ["01_", "02_", "03_", "04_", "05_"]:
            if task_id.startswith(prefix):
                task_id = task_id[len(prefix):]
                break
        result = TaskResult(task_id, agent_name)

        try:
            proc = subprocess.run(
                [sys.executable, str(score_script), workdir],
                capture_output=True, text=True, timeout=60,
                cwd=str(task_dir)
            )
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                result.score = data.get("score", 0)
                result.max_score = data.get("max", 1)
                result.details = data.get("details", [])
                result.evidence = data.get("evidence", {})
            else:
                result.add_fail(f"score.py 执行失败", 5, proc.stderr[:200])
        except Exception as e:
            result.add_fail(f"score.py 异常", 5, str(e))

        all_results.append(result)

    # 输出结果
    report = print_summary(all_results, agent_name)
    print(report)

    # 保存 JSON 结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = RESULTS_DIR / f"{agent_name}_{ts}.json"
    outfile.write_text(json.dumps([r.to_dict() for r in all_results], indent=2, ensure_ascii=False))
    print(f"\n📁 详细结果: {outfile}")
