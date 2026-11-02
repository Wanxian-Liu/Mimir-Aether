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


# ─────────────────────────────────────────────────────────────────────────────
# 观测档（2026-10-26 三条反馈 · 刘哥 2026-11-02 批示：先只加观测日志，
# 零行为变更 —— 不额外等一周才开始收读数）
#
# 边界（写死，别日后改顺手）：
#   * 本段**不参与**触发判定——`estimate_parallel_elig` / `parallel_elig_ok` 一行不改；
#     `pi_trigger` 只读 `explain_parallel_elig()` 的返回值写 hook 日志。
#   * 三档（A 强结构=2 / B 量化动作=1 / C 散文=1，MIN=2）**尚未生效**——要等观测读数
#     支持后再改判据（Step②）。
#   * `classify_step_type()` 是「编号枚举带 首先/然后/最后 ≥2 次 ⇒ 判步骤型不给分」
#     那条判据的**可跑断言**载体（刘哥批示：改判据前先写成可跑断言）。
# ─────────────────────────────────────────────────────────────────────────────

# A 档：强结构信号的计分（单条即过 MIN=2）
STRUCT_SCORE = 2
# 枚举判定的最少项数（与 A2「≥3 项且同层」一致）
ENUM_MIN_ITEMS = 3

# 步骤型判别词（刘哥逐字点名：首先/然后/最后；其余为同族，一并计入）
STEP_WORDS = ("首先", "其次", "然后", "接着", "最后",
              "第一步", "第二步", "步骤", "step")

# 枚举行：`1.` / `1、` / `1)` / `（1）` / `- ` / `* ` / `+ `
_ENUM_LINE_RE = re.compile(
    r"^\s*(?:\d+\s*[.、)）]|[(（]\s*\d+\s*[)）]|[-*+]\s+)\s*\S", re.MULTILINE
)
_CHECKBOX_RE = re.compile(r"^\s*-\s+\[[ xX]\]", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)

# B 档：量化动作信号
_TOOL_NAMES = ("web_search", "web_extract", "grep", "read_file", "write_file",
               "terminal", "execute_code", "delegate_task", "patch", "browser")
_PATH_TOKEN_RE = re.compile(
    r"(?:~|\.{0,2}/)?[\w][\w.\-/]*\.(?:md|markdown|py|sh|json|jsonl|txt|pdf|docx|db|log|csv|ya?ml)"
)
_MULTI_TARGET_WORDS = ("多库", "多主机", "多 URL", "多url", "多个库", "多个主机")


def classify_step_type(task_spec: str) -> dict:
    """判「编号枚举」是不是**步骤型串行链**（形状相同、语义相反的关键区分口）。

    判据（刘哥 2026-10-26 批 · 逐字）：
        编号/项目符号枚举 ≥3 项（同层） ∧ 步骤词（首先/然后/最后 …）出现 ≥2 次
        ⇒ 步骤型 ⇒ A2 不给分

    为什么必须单列：`S1…S10 并列编号`（可并行派单）与 `施工步骤书 1→5`
    （串行依赖链）在形状上完全一样，只看形状必然误判。

    Returns:
        {"enum_items": int, "step_words": int, "is_step_type": bool,
         "hits": [str, ...]}   # hits 供人工复核「它凭什么这么判」
    """
    spec = task_spec or ""
    lines = [ln for ln in spec.splitlines() if ln.strip()]

    enum_items = 0
    for ln in lines:
        if _CHECKBOX_RE.match(ln):
            continue                             # checkbox 归 A1，不计入 A2 枚举项
        if _ENUM_LINE_RE.match(ln) and not ln.strip().startswith("|"):
            enum_items += 1                      # 纯表格行不算枚举项（A3 单独判）

    low = spec.lower()
    # 计数口径 = **出现次数**（刘哥逐字「≥2 次」）——不是「不同词数」：
    #   「接着…再接着…」是同一词 2 次，语义上仍是串行叙述（selftest N5 实证漏判）。
    step_hits = []
    n_step = 0
    for w in STEP_WORDS:
        c = low.count(w)
        if c:
            n_step += c
            step_hits.append(w)

    is_step = (enum_items >= ENUM_MIN_ITEMS) and (n_step >= 2)
    hits = []
    if enum_items:
        hits.append("enum:%d项" % enum_items)
    if n_step:
        hits.append("step词:%d(%s)" % (n_step, ",".join(step_hits[:4])))
    if is_step:
        hits.append("步骤型")
    return {
        "enum_items": enum_items,
        "step_words": n_step,
        "is_step_type": is_step,
        "hits": hits,
    }


def explain_parallel_elig(task_spec: str) -> dict:
    """三档口径的**观测**计算（只出读数，不改触发行为）。

    三档（提案 · 未生效）：
        A 强结构   = 2  A1 `- [ ]` ≥3 · A2 编号/项目符号枚举 ≥3 且**非步骤型** ·
                        A3 表格 ≥3 行且首列对象不同（单条即过 MIN）
        B 量化动作 = 1  B1 不同文件路径 ≥3 · B2 不同工具名 ≥3 · B3 不同目标源 ≥2
        C 散文推断 = 1  现有三关键词（多源/批量/独立）——只在无 A/B 时生效
        MIN = MIMIR_PI_MIN_PARALLEL（默认 2）

    Returns:
        {"elig": 现判据分值（与 estimate_parallel_elig 恒等）,
         "elig_struct": A 档得分（0 或 2）, "elig_kw": B+C 得分（0..2）,
         "would_trigger": 三档口径下是否会触发（bool，仅观测）,
         "step_type": 是否步骤型,
         "hits": "A2:枚举9项;B1:路径12" 形式的可解释串}
    """
    spec = task_spec or ""
    cur = estimate_parallel_elig(spec)   # 现口径真值——只记录，不回写
    if not spec.strip():
        return {"elig": cur, "elig_struct": 0, "elig_kw": 0,
                "would_trigger": False, "step_type": False, "hits": ""}

    hits = []

    # ── A 档（结构优先：命中即 2，不累加）───────────────────────────────
    struct = 0
    cb = _CHECKBOX_RE.findall(spec)
    if len(cb) >= ENUM_MIN_ITEMS:
        struct = STRUCT_SCORE
        hits.append("A1:checkbox%d" % len(cb))
    if not struct:
        st = classify_step_type(spec)
        if st["enum_items"] >= ENUM_MIN_ITEMS and not st["is_step_type"]:
            struct = STRUCT_SCORE
            hits.append("A2:枚举%d项" % st["enum_items"])
        elif st["is_step_type"]:
            hits.append("A2:毙(步骤型%d词)" % st["step_words"])
    if not struct:
        trows = _TABLE_ROW_RE.findall(spec)
        if len(trows) >= ENUM_MIN_ITEMS + 1:      # 表头 + 分隔 + ≥2 行体
            firsts = set()
            for ln in trows:
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if cells and cells[0] and not set(cells[0]) <= set("-: "):
                    firsts.add(cells[0])
            if len(firsts) >= ENUM_MIN_ITEMS:
                struct = STRUCT_SCORE
                hits.append("A3:表格首列%d" % len(firsts))

    # ── B 档（量化动作——独立动作才计）──────────────────────────────────
    b_hit = 0
    paths = set(_PATH_TOKEN_RE.findall(spec))
    if len(paths) >= 3:
        b_hit = 1
        hits.append("B1:路径%d" % len(paths))
    tools = {t for t in _TOOL_NAMES if t in spec}
    if len(tools) >= 3:
        b_hit = 1
        hits.append("B2:工具%d" % len(tools))
    urls = re.findall(r"https?://", spec)
    if len(urls) >= 2 or any(w in spec for w in _MULTI_TARGET_WORDS):
        b_hit = 1
        hits.append("B3:目标源%d" % max(len(urls), 2))

    # ── C 档（散文推断——只在无 A/B 时生效）────────────────────────────
    c_hit = 0
    if not struct and not b_hit:
        if (any(s in spec for s in _MULTI_SOURCE_SIGNALS)
                or any(s in spec for s in _BATCH_SIGNALS)
                or any(s in spec for s in _INDEPENDENT_SIGNALS)):
            c_hit = 1
            hits.append("C:散文关键词")

    kw = b_hit + c_hit
    threshold = int(os.getenv("MIMIR_PI_MIN_PARALLEL", "2") or "2")
    would = (threshold > 0) and (struct + kw >= threshold)
    st = classify_step_type(spec)
    return {
        "elig": cur,
        "elig_struct": struct,
        "elig_kw": kw,
        "would_trigger": bool(would),
        "step_type": bool(st["is_step_type"]),
        "hits": ";".join(hits)[:160],
    }


__all__ = [
    "estimate_parallel_elig",
    "parallel_elig_ok",
    "classify_step_type",
    "explain_parallel_elig",
    "STRUCT_SCORE",
    "ENUM_MIN_ITEMS",
    "STEP_WORDS",
]
