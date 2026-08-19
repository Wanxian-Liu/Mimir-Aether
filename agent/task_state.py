"""TaskState — Mimir 任务状态枚举（四方调研审计共识，2026-08-05）。

来源：discussions/Mimir task_state专项-四方调研审计.md
设计：PROBING | WRITING | VERIFYING | DONE（最小可行，验证有效再扩展）

LangChain 2026 State of Agent Engineering 报告：60%+ 生产 agent 事故源于状态管理。
Mimir 四守卫（intent/verify/search/interval）已是隐式状态机，缺的是显式总线。
"""

from enum import Enum


class TaskState(str, Enum):
    """Mimir 任务执行状态——各模块（nudge/压缩器/退出条件/save）据此感知任务在做什么。

    - PROBING:   探测/调研阶段（read_file/search_files/web_search）
    - WRITING:   写盘阶段（write_file/patch 已调用）——nudge 跳过、压缩器延迟
    - VERIFYING: 验证阶段（verify guard 放行/回读）
    - DONE:      自然退出（只有 DONE 才允许自然结束，防"假完成"）
    - INTERRUPTED: TD-03 L3 中断（2026-08-18 四方批准·Hermes代改）——连续硬拦截后仍无产出，
      任务未完成被中断。消费方不得当 DONE/IN_PROGRESS 处理（防隐式卡死）。
    - TASK_COMPLETE: 任务书完成度检查通过（2026-08-19 四方会议 Loki B-L5）——任务真正完成。
      区分"自然结束（DONE）" vs "任务完成（TASK_COMPLETE）"：有任务书（含子步骤清单）且
      全部完成时标注 TASK_COMPLETE；无任务书的纯问答自然退出仍标 DONE（旧语义）。
    """

    PROBING = "probing"
    WRITING = "writing"
    VERIFYING = "verifying"
    DONE = "done"
    INTERRUPTED = "interrupted"
    TASK_COMPLETE = "task_complete"  # 四方会议 2026-08-19（Loki B-L5）：任务书完成度检查通过——任务真正完成

    @classmethod
    def from_tool_name(cls, tool_name: str) -> "TaskState | None":
        """按工具名推断状态（注入点用——最小侵入）。

        写盘工具 → WRITING；探测工具 → PROBING；其余 → None（不改变状态）。
        """
        WRITE_TOOLS = {"write_file", "patch", "apply_patch", "edit"}
        PROBE_TOOLS = {"read_file", "search_files", "web_search", "grep"}
        if tool_name in WRITE_TOOLS:
            return cls.WRITING
        if tool_name in PROBE_TOOLS:
            return cls.PROBING
        return None
