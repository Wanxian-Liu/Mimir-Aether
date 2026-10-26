"""parallel_eligibility.py — 任务可并行度估计（块3·段2·K1·2026-08-20）。

设计来源（盘上参照）：
- 段 1 触发公式（四方卡 L3584+）：委派触发 = (est_turns>=8) AND (parallel_elig>=MIN_PARALLEL) AND (反向清单通过)
- OpenClaw 定义（L2370-2375）：parallel_elig 三信号——①多源调用 ②批量 grep ③独立子任务 3+ 项
- Mimir K1（审计）：parallel_elig 是"纸上变量"——代码 0 命中——本模块补上"函数"

边界（段 1 记录）：
- 依赖关键词反向过滤：子步骤含"之后/然后/基于/依赖/顺序" → 标记串行 → 不算可并行
- env MIMIR_PI_MIN_PARALLEL（默认 2）——0 = 回退（不触发——调用方判断）
"""

import os
import re

# 三信号关键词（保守——宁漏勿滥）
_MULTI_SOURCE_SIGNALS = ("web_search", "web_extract", "多源", "多个来源", "分别搜索", "分别查", "多url", "多 URL")
_BATCH_SIGNALS = ("批量", "多个文件", "多文件", "grep", "遍历", "循环处理", "批量验证", "同模式")
_INDEPENDENT_SIGNALS = ("3 个", "3个", "多项", "分别", "各自", "独立", "同时", "并行")

# 依赖关键词（反向——串行信号）
# 2026-10-26 根因 D2：单字「逐」移出——它在 pi_trigger._LONG_TASK_HINTS 里是
#   遍历/并行信号（逐条/逐张/逐项/逐一），同一字两模块语义相反 = 词表冲突。
_DEPENDENCY_SIGNALS = ("之后", "然后", "基于", "依赖", "顺序", "接着", "下一步", "依次")


def estimate_parallel_elig(task_spec: str) -> int:
    """从任务书提取可并行信号——返回满足条件数（≥MIMIR_PI_MIN_PARALLEL 触发委派）。

    三信号（满足即 +1）：
      ① 多源调用（web_search/web_extract 多 URL/多源调研字样）
      ② 批量信号（多文件同模式 grep/批量验证）
      ③ 独立子任务（- [ ] 清单 ≥3 项 或 独立/同时/并行 字样）

    依赖关键词反向过滤：任务书整体含强依赖信号（之后/然后/基于/依赖/顺序）→
    子步骤实为串行链——parallel_elig 视为 0（不委派）。

    Returns:
        int: 0-3（满足条件数——调用方与 MIMIR_PI_MIN_PARALLEL 比较）
    """
    if not task_spec or not task_spec.strip():
        return 0

    spec = task_spec

    # 显式结构探测（2026-10-26 根因 D2）：- [ ] 清单 ≥3 项 = 作者已枚举独立子任务
    _checkboxes = re.findall(r"^-\s+\[[ xX]\]", spec, re.MULTILINE)
    _has_explicit_structure = len(_checkboxes) >= 3

    # 依赖反向过滤（K1 核心——串行任务不算可并行）
    # D2 修正：仅在**无显式结构**的整块 blob 上生效。显式 checkbox 清单 ≥3 项时，
    #   正文里的「然后/之后」只是叙述顺序，不是子任务依赖链——旧判据把
    #   「3 checkbox + 分别 + grep」的教科书式并行派单一刀 return 0（实证）。
    if not _has_explicit_structure:
        _dep_hits = sum(1 for d in _DEPENDENCY_SIGNALS if d in spec)
        if _dep_hits >= 2:
            return 0  # 强依赖链（"之后/然后/基于" 出现 2+ 次）→ 串行——不委派

    elig = 0

    # 信号①：多源调用
    if any(s in spec for s in _MULTI_SOURCE_SIGNALS):
        # 多 URL 检测（http 链接 ≥2 个）
        _urls = re.findall(r"https?://", spec)
        if len(_urls) >= 2:
            elig += 1
        elif any(s in spec for s in ("多源", "多个来源", "分别搜索")):
            elig += 1

    # 信号②：批量
    if any(s in spec for s in _BATCH_SIGNALS):
        elig += 1

    # 信号③：独立子任务（- [ ] 清单 ≥3 项 或 独立/同时/并行 字样）
    # （_checkboxes / _has_explicit_structure 在上方已探测——D2 复用，不二次重算）
    if _has_explicit_structure:
        elig += 1
    elif any(s in spec for s in ("独立", "同时", "并行", "分别")):
        elig += 1

    return elig


def parallel_elig_ok(task_spec: str) -> bool:
    """段 1 公式第 2 变量判定：parallel_elig >= MIMIR_PI_MIN_PARALLEL。

    env: MIMIR_PI_MIN_PARALLEL（默认 2）——0 = 回退（恒 False——不触发委派）
    """
    threshold = int(os.getenv("MIMIR_PI_MIN_PARALLEL", "2") or "2")
    if threshold <= 0:
        return False
    return estimate_parallel_elig(task_spec) >= threshold
