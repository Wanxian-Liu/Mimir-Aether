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
    regression_cmd: str = ""      # #2 回归保护：gate通过后必须跑的命令
    belief_callback: object = None  # #1 LLM驱动信念归因: fn(round, hyp, pred_Δ, real_Δ, beliefs) → new_beliefs


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


# ============================================================
# Causal AR Buffer — TASKLOOP_ARCH.md §8.8
# Paper: "Efficient Autoregressive Inference for Transformer
#  Probabilistic Models" (Conor et al., 2025, arXiv:2510.09477v2)
# ============================================================

@dataclass
class ContextCache:
    """R1: 上下文固化，一次编码不可变。
    
    对应论文 r_C(C) — 上下文编码后缓存为只读。
    TaskLoop 中 = program.md + config 的压缩摘要。
    """
    summary: str                          # 压缩版任务描述 (~100 tokens)
    no_go: list[str] = field(default_factory=list)
    created_at: float = 0.0


@dataclass
class BeliefEntry:
    """R2: Buffer 条目，严格因果。
    
    第 k 轮只能看到 < k 的条目。
    每个条目 = 假设 + 分数变化 + 一句话教训。
    """
    round: int
    hypothesis: str                       # 1行: "扩展 OOM 的 cause 条目"
    score_delta: float                    # 度量: +0.015
    lesson: str                           # 1行信仰: "丰富 cause 比加 code 有效"


class BeliefsBuffer:
    """R2/R4: 信念缓冲区。
    
    R2: 严格因果 — visible_prefix(k) 只返回 < k 的条目。
    R4: 目标间不自注意 — 各自看缓存+buffer前缀。
    MAX_SIZE: 20 条（与社区实践一致）。
    """
    MAX_SIZE = 20

    def __init__(self):
        self.entries: list[BeliefEntry] = []

    def append(self, entry: BeliefEntry):
        """追加信念，超出上限时移除最旧条目（FIFO）。"""
        self.entries.append(entry)
        if len(self.entries) > self.MAX_SIZE:
            self.entries = self.entries[-self.MAX_SIZE:]

    def visible_prefix(self, k: int) -> list[BeliefEntry]:
        """第 k 轮只能看到 < k 的条目（R2 因果约束）。"""
        return [e for e in self.entries if e.round < k]

    def format_for_llm(self, k: int) -> str:
        """将可见 prefix 格式化为 LLM 可读文本。"""
        visible = self.visible_prefix(k)
        if not visible:
            return ""
        lines = ["## 信念缓冲区 (已学教训)", ""]
        for e in visible:
            sign = "+" if e.score_delta >= 0 else ""
            lines.append(
                f"- R{e.round}: {e.hypothesis} "
                f"(Δ{sign}{e.score_delta:.4f}) — {e.lesson}"
            )
        return "\n".join(lines)

    def rewrite_from_text(self, beliefs_text: str, round_num: int = 0):
        """#1: LLM驱动的信念重写 — 不追加，完全替换。
        
        对应 Discussion #340: Agent 每轮重写 beliefs.md，不追加。
        输入: LLM 生成的信仰文本（每行一条 "- xxx"）。
        """
        self.entries = []
        for line in beliefs_text.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("- "):
                continue
            content = line[2:]  # 去掉 "- "
            entry = BeliefEntry(
                round=round_num,
                hypothesis="",
                score_delta=0.0,
                lesson=content,
            )
            self.entries.append(entry)
        if len(self.entries) > self.MAX_SIZE:
            self.entries = self.entries[-self.MAX_SIZE:]

    def __len__(self):
        return len(self.entries)

    def __bool__(self):
        return len(self.entries) > 0
