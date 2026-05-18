"""
TaskLoop 数据结构定义 — 无外部依赖，纯 stdlib。

BACKLOG #5 | 与 TASKLOOP_ARCH.md §2 对齐
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StopReason(Enum):
    TARGET_REACHED = "目标达成"
    ROUNDS_EXHAUSTED = "轮次耗尽"
    TIME_EXHAUSTED = "时间耗尽"
    DEGENERATION = "连续退化"
    DEAD_END = "死胡同"
    SAFETY = "安全风险"


class CrashTier(Enum):
    """崩溃分级 — TASKLOOP_ARCH.md §4.1"""
    DUMB = 1       # typo/缺import/语法错 → 修完继续，不占轮次
    HARD = 2       # OOM/超时/架构崩 → reset，记录crash，下轮
    LLM_FAIL = 3   # API超时/429 → 重试1次 → 仍失败 → DEAD_END


@dataclass
class TaskLoopConfig:
    """任务配置 — 启动时传入。TASKLOOP_ARCH.md §2.1"""
    task: str                     # "优化 capsule 生成质量，目标 GDI≥70"
    eval_cmd: str                 # shell命令，stdout末行必须是数值
    target_score: float           # 目标分数
    max_rounds: int = 20          # 最大轮次
    max_time: int = 600           # 总时间预算(秒)
    eval_timeout: int = 300       # 单次评测超时(秒) — Karpathy: 5min
    no_go: list[str] = field(default_factory=list)  # 禁区
    workdir: str = "."            # 工作目录
    min_delta: float = 0.001      # 有效提升的最小Δ（防浮点噪声）


@dataclass
class RoundState:
    """轮次状态 — 写入 results.tsv 的行。TASKLOOP_ARCH.md §2.2"""
    round: int
    hypothesis: str               # "把 chunk_size 从 512 改到 1024"
    score: float
    delta: float                  # 相比上轮 best_score 的提升
    passed: bool
    duration_s: float
    commit_hash: Optional[str] = None
    error: Optional[str] = None
    lines_changed: int = 0        # 本轮改动行数（简洁判据用）


@dataclass
class LoopState:
    """循环全局状态"""
    best_score: float = 0.0
    best_round: int = 0
    consecutive_fails: int = 0    # 连续退化计数
    rounds_completed: int = 0
    start_time: float = 0.0
    stop_reason: Optional[StopReason] = None


@dataclass
class TaskLoopResult:
    """循环结束后汇总"""
    rounds: list[RoundState]
    stop_reason: StopReason
    best_score: float
    best_round: int
    total_rounds: int
    total_time_s: float
    commits: list[str] = field(default_factory=list)
