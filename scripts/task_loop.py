"""
TaskLoop 执行引擎 — 原型

BACKLOG #5 | 与 TASKLOOP_ARCH.md §3-4 对齐

用法:
    python3 scripts/task_loop.py --config config.json
    python3 scripts/task_loop.py --demo              # 演示模式
"""

import subprocess
import time
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from .task_loop_config import (
    TaskLoopConfig, RoundState, StopReason, CrashTier,
    LoopState, TaskLoopResult,
)


# ============================================================
# §4.1 崩溃分级
# ============================================================

class CrashClassifier:
    """三梯级崩溃识别 — TASKLOOP_ARCH.md §4.1"""

    DUMB_PATTERNS = [
        r"SyntaxError", r"IndentationError", r"NameError",
        r"ImportError", r"ModuleNotFoundError", r"AttributeError.*has no attribute",
        r"TypeError.*missing.*argument", r"FileNotFoundError.*No such file",
    ]
    HARD_PATTERNS = [
        r"MemoryError", r"CUDA out of memory", r"OOM",
        r"ConnectionError", r"Timeout", r"timed out",
        r"Segmentation fault", r"Killed", r"signal",
        r"RuntimeError.*CUDA", r"bus error",
    ]

    @classmethod
    def classify(cls, error_text: str) -> CrashTier:
        text = str(error_text)
        for pat in cls.DUMB_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return CrashTier.DUMB
        for pat in cls.HARD_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return CrashTier.HARD
        return CrashTier.HARD  # 未知崩溃默认硬崩溃


# ============================================================
# §4.2 简洁判据
# ============================================================

def gate_pass(config: TaskLoopConfig, score: float, best_score: float,
              lines_changed: int) -> tuple[bool, str]:
    """判断本轮是否值得保留 — TASKLOOP_ARCH.md §4.2"""
    delta = score - best_score

    if delta < 0:
        return False, f"Δ={delta:.4f}<0 → discard"

    if delta == 0 and lines_changed <= 0:
        return True, ""  # 等效简化

    if delta == 0 and lines_changed > 0:
        return False, f"Δ=0 且 +{lines_changed}行 → 不值得"

    if lines_changed <= 10:
        return True, ""  # 简洁改进

    if lines_changed > 30 and delta < 0.005:
        return False, f"改动过大({lines_changed}行)且Δ过小({delta:.4f})"

    return True, ""


# ============================================================
# §3.3 评测运行器
# ============================================================

def run_eval(cmd: str, timeout: int = 300, workdir: str = ".") -> tuple[float, bool, float, str]:
    """运行评测命令，返回(score, ok, duration, error)。

    超时自动kill，stdout末行为数值。
    """
    start = time.time()
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=workdir,
        )
        duration = time.time() - start

        if proc.returncode != 0:
            return -1, False, duration, proc.stderr[:500] or f"exit={proc.returncode}"

        # 从stdout提取最后一个数值
        stdout = proc.stdout.strip()
        # 找最后一行里的浮点数
        lines = stdout.split("\n")
        for line in reversed(lines):
            nums = re.findall(r"[-+]?\d*\.?\d+", line)
            if nums:
                return float(nums[-1]), True, duration, ""

        return -1, False, duration, "stdout中没有数值"

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return -1, False, duration, f"超时({timeout}s)"


# ============================================================
# §3.4 停止条件
# ============================================================

class StopChecker:
    """停止条件引擎 — TASKLOOP_ARCH.md §2.3"""

    MAX_CONSECUTIVE_FAILS = 3  # 连续退化→DEGENERATION

    @classmethod
    def check(cls, config: TaskLoopConfig, rounds: list[RoundState],
              best_score: float, elapsed: float,
              consecutive_fails: int) -> tuple[bool, Optional[StopReason]]:

        # 目标达成
        if best_score >= config.target_score:
            return True, StopReason.TARGET_REACHED

        # 轮次耗尽
        if len(rounds) >= config.max_rounds:
            return True, StopReason.ROUNDS_EXHAUSTED

        # 时间耗尽
        if elapsed >= config.max_time:
            return True, StopReason.TIME_EXHAUSTED

        # 连续退化
        if consecutive_fails >= cls.MAX_CONSECUTIVE_FAILS:
            return True, StopReason.DEGENERATION

        return False, None


# ============================================================
# results.tsv 记录
# ============================================================

def append_result(path: str, round_state: RoundState):
    """追加一行到 results.tsv"""
    exists = Path(path).exists()
    with open(path, "a") as f:
        if not exists:
            f.write("round\thypothesis\tscore\tdelta\tpassed\tduration_s\tlines_changed\terror\n")
        f.write(f"{round_state.round}\t{round_state.hypothesis}\t"
                f"{round_state.score:.4f}\t{round_state.delta:.4f}\t"
                f"{round_state.passed}\t{round_state.duration_s:.1f}\t"
                f"{round_state.lines_changed}\t{round_state.error or ''}\n")


# ============================================================
# Git 操作
# ============================================================

def git_commit(message: str, workdir: str = ".") -> Optional[str]:
    """提交并返回 hash，失败返回 None"""
    try:
        subprocess.run(["git", "add", "-A"], cwd=workdir, capture_output=True, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=workdir, capture_output=True, text=True, check=True,
        )
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workdir, capture_output=True, text=True, check=True,
        )
        return hash_result.stdout.strip()[:8]
    except subprocess.CalledProcessError:
        return None


def git_reset_hard(workdir: str = "."):
    """硬回滚到上次 commit"""
    subprocess.run(["git", "reset", "--hard"], cwd=workdir, capture_output=True)


# ============================================================
# 汇总报告
# ============================================================

def summarize(rounds: list[RoundState], result: TaskLoopResult) -> str:
    """生成人类可读的循环报告"""
    lines = [
        "=" * 60,
        "  TaskLoop 执行完毕",
        "=" * 60,
        f"  停止原因: {result.stop_reason.value}",
        f"  总轮次:   {result.total_rounds}",
        f"  总耗时:   {result.total_time_s:.0f}s",
        f"  最佳分数: {result.best_score:.4f} (第{result.best_round}轮)",
    ]

    if rounds:
        lines.append("")
        lines.append("  轮次详情:")
        for r in rounds:
            flag = "✅" if r.passed else "❌"
            lines.append(f"    {flag} R{r.round}: {r.score:.4f} (Δ{r.delta:+.4f}) — {r.hypothesis[:60]}")

    lines.append("=" * 60)
    return "\n".join(lines)


# ============================================================
# 主循环
# ============================================================

def run(config: TaskLoopConfig, strategy_fn=None) -> TaskLoopResult:
    """主循环 — TASKLOOP_ARCH.md §3.1

    strategy_fn(rounds, best_score, config) → (hypothesis, changes_dict, error)
    如果为 None，使用演示模式（随机探索）。
    """
    loop = LoopState(start_time=time.time())
    rounds: list[RoundState] = []
    classifier = CrashClassifier()

    # 运行基线
    score, ok, dur, err = run_eval(config.eval_cmd, config.eval_timeout, config.workdir)
    if ok:
        loop.best_score = score
        print(f"[基线] score={score:.4f}")
    else:
        loop.best_score = 0.0
        print(f"[基线] 失败: {err[:80]}")

    round_num = 0
    while True:
        elapsed = time.time() - loop.start_time

        # 停止检查
        stop, reason = StopChecker.check(
            config, rounds, loop.best_score, elapsed, loop.consecutive_fails)
        if stop:
            loop.stop_reason = reason
            break

        round_num = len(rounds) + 1

        # ① 策略 (LLM 或演示模式)
        if strategy_fn:
            hypothesis, changes, strategy_err = strategy_fn(rounds, loop.best_score, config)
        else:
            hypothesis, changes, strategy_err = _demo_strategy(round_num)

        if strategy_err:
            tier = classifier.classify(strategy_err)
            if tier == CrashTier.LLM_FAIL:
                loop.stop_reason = StopReason.DEAD_END
                break
            # 其他策略错误也算硬崩溃
            rounds.append(RoundState(
                round=round_num, hypothesis=hypothesis,
                score=-1, delta=0, passed=False,
                duration_s=0, error=f"strategy: {strategy_err[:100]}",
                lines_changed=0,
            ))
            loop.consecutive_fails += 1
            continue

        # 应用修改
        lines_changed = _apply_changes(changes, config.workdir)

        # ② 评测
        score, ok, dur, eval_err = run_eval(
            config.eval_cmd, config.eval_timeout, config.workdir)

        if not ok:
            tier = classifier.classify(eval_err)

            if tier == CrashTier.DUMB:
                # 哑崩溃: 尝试修 → 重跑 (简化: 标记但继续)
                print(f"[R{round_num}] 哑崩溃 — {eval_err[:60]}")
                loop.consecutive_fails += 0  # 不计数

            rounds.append(RoundState(
                round=round_num, hypothesis=hypothesis,
                score=-1, delta=0, passed=False,
                duration_s=dur, error=eval_err[:200],
                lines_changed=lines_changed,
            ))

            if tier == CrashTier.HARD:
                git_reset_hard(config.workdir)
                loop.consecutive_fails += 1
                print(f"[R{round_num}] 硬崩溃 → reset — {eval_err[:60]}")
            continue

        # ③ 门控
        delta = score - loop.best_score
        kept, warn = gate_pass(config, score, loop.best_score, lines_changed)

        commit_hash = None
        if kept:
            if delta >= config.min_delta or (delta == 0 and lines_changed <= 0):
                commit_hash = git_commit(
                    f"R{round_num}: {hypothesis} (score={score:.4f})",
                    config.workdir,
                )
                loop.best_score = score
                loop.best_round = round_num
                loop.consecutive_fails = 0
            else:
                pass  # Δ太小但简洁改进
        else:
            git_reset_hard(config.workdir)
            loop.consecutive_fails += 1
            if warn:
                print(f"[R{round_num}] gate reject: {warn}")

        # ④ 记录
        rs = RoundState(
            round=round_num, hypothesis=hypothesis,
            score=score, delta=delta, passed=kept,
            duration_s=dur, commit_hash=commit_hash,
            error=warn or eval_err,
            lines_changed=lines_changed,
        )
        rounds.append(rs)
        append_result(f"{config.workdir}/data/results.tsv", rs)

        print(f"[R{round_num}] {'✅' if kept else '❌'} "
              f"score={score:.4f} Δ={delta:+.4f} "
              f"best={loop.best_score:.4f} "
              f"({dur:.0f}s) — {hypothesis[:50]}")

    # 汇总
    result = TaskLoopResult(
        rounds=rounds,
        stop_reason=loop.stop_reason or StopReason.ROUNDS_EXHAUSTED,
        best_score=loop.best_score,
        best_round=loop.best_round,
        total_rounds=len(rounds),
        total_time_s=time.time() - loop.start_time,
    )
    print(summarize(rounds, result))
    return result


# ============================================================
# 演示模式
# ============================================================

def _demo_strategy(round_num: int) -> tuple[str, dict, Optional[str]]:
    """演示策略生成器 — 随机探索模型参数"""
    import random
    params = [
        ("temperature", round(random.uniform(0.1, 1.5), 2)),
        ("top_p", round(random.uniform(0.5, 1.0), 2)),
        ("max_tokens", random.choice([512, 1024, 2048, 4096])),
        ("chunk_size", random.choice([256, 512, 1024])),
        ("overlap", random.choice([0, 50, 100, 200])),
        ("penalty", round(random.uniform(0, 2.0), 2)),
    ]
    param, value = random.choice(params)
    hypothesis = f"设置 {param} = {value}"
    changes = {"params.py": f"{param.upper()} = {value}\n"}
    return hypothesis, changes, None


def _apply_changes(changes: dict, workdir: str) -> int:
    """应用修改，返回改动的行数。简化版：写文件。"""
    total_lines = 0
    for filepath, content in changes.items():
        full_path = Path(workdir) / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        total_lines += content.count("\n")
    return total_lines


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    if "--demo" in sys.argv or "-d" in sys.argv:
        config = TaskLoopConfig(
            task="演示: 随机参数探索",
            eval_cmd="python3 -c 'import random; print(random.uniform(0.5, 1.0))'",
            target_score=0.99,
            max_rounds=5,
            max_time=120,
        )
        run(config)
    elif "--config" in sys.argv or "-c" in sys.argv:
        idx = sys.argv.index("--config") if "--config" in sys.argv else sys.argv.index("-c")
        path = sys.argv[idx + 1]
        with open(path) as f:
            data = json.load(f)
        config = TaskLoopConfig(**data)
        run(config)
    else:
        print("用法: python3 -m scripts.task_loop --demo")
        print("      python3 -m scripts.task_loop --config <path>")
