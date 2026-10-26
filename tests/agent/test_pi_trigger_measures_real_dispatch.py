"""PI 触发「测量对象」回归用例（2026-10-26 · 根因修复 D1/D2）

病灶（取证卡：~/wiki/discussions/2026-10-26-PI子代理未触发-根因取证-mimir.md）：
1. `agent_loop` turn 0 先把 `<intent-context>` **以 role=user 追加**进 messages，
   再调 `maybe_pi_delegate_execute(messages)`；`pi_trigger._extract_user_task` 只跳过
   `"[MIMIR_"` / `"[CONTEXT"` ⇒ 把 210 字符的 intent 注入块当「用户派单」打分
   ⇒ `est` 恒 = 4（实证：55/55 次 est=4 都紧邻 `intent-context injected`）。
2. `parallel_eligibility` 的依赖词过滤在全文命中 2+ 次即 `return 0`，且词表里含单字「逐」
   （该字在 `pi_trigger._LONG_TASK_HINTS` 里是遍历/并行信号）⇒ 显式 3 checkbox 的
   教科书式并行派单也拿 0。

本用例 = 两向：正控（真派单该过） + 负控（注入块不得被选中；无结构强依赖仍拦）。
"""
import os
import sys

sys.path.insert(0, os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from agent.pi_trigger import _estimate_turns, _extract_user_task  # noqa: E402
from agent.parallel_eligibility import estimate_parallel_elig, parallel_elig_ok  # noqa: E402
from agent.injection_prefixes import (  # noqa: E402
    INJECTION_PREFIXES,
    PI_TASK_SKIP_PREFIXES,
    is_injected,
    is_injected_pi,
)

# 与线上注入块同形（agent_loop line 494-515 产出物）
INTENT_CTX = (
    "<intent-context> intent=code complexity=complex confidence=0.75 "
    "Prefer session_search (or read_file) before answering from memory alone.\n"
    "Grounded task: use tools in this turn; do not defer with text-only plans."
)

# 与线上空跑闸门注入块同形（中文方括号族，A1 漏项）
GATE_CTX = (
    "【空跑闸门】本 run 已连续 4 轮只读（预算 4）且**交付物未写**——本轮**必须**先落盘再继续："
    "用 write_file/patch 把已读材料落成**半段**交付物，写完再补证。"
)

# 真实长中文派单（含 checkbox + 多源 + 批量信号）
REAL_DISPATCH = """【任务】PI 子代理触发链根因取证与修复

【背景】日志读数：est 恒 4、min_turns=8、spawn 计数 0。请按下列步骤执行：

- [ ] 扫一遍 ~/.mimiraether/logs/agent.log，统计 est 分布与 nudge 决策分布
- [ ] 分别核对 agent/pi_trigger.py 中 _extract_user_task 的取值口径
- [ ] 逐个检查 agent/parallel_eligibility.py 的三信号与依赖过滤，写成对照表
- [ ] 汇总成取证卡，附可复跑的 grep 命令

【边界】只写自己域内的取证与修复；不改 subagent_bridge 的 spawn 协议。
"""


# ── 负控 1：注入块指纹（est=4 的来源，改动前后都应等于 4）────────────────────
def test_injection_block_fingerprint_is_4():
    assert _estimate_turns(INTENT_CTX) == 4, "intent 注入块的指纹 est 应是 4（历史 55/55 病灶来源）"
    # 空跑闸门块同样绝无可能过阈值（长度/信号都不够）
    assert _estimate_turns(GATE_CTX) < 8


# ── 负控 2：注入块必须被识别为注入；真派单（【任务】起头）**不得**被吞 ───────
def test_injection_blocks_are_recognised():
    assert is_injected(INTENT_CTX) is True
    assert is_injected(GATE_CTX) is True
    assert is_injected_pi(INTENT_CTX) is True
    assert is_injected_pi(GATE_CTX) is True
    # 正控核心：「【任务】」起头的真派单，PI 口径**不是**注入
    assert is_injected_pi(REAL_DISPATCH) is False, "真派单被当注入 ⇒ est 量不到 ⇒ PI 恒不触发"
    # 负控兜底：窄表绝不可包含 【任务】/【架构（回归锁死——勿再塞回去）
    for bad in ("【任务】", "【架构"):
        assert bad not in PI_TASK_SKIP_PREFIXES, f"{bad} 不得进入 PI 跳过表"
    for p in ("[MIMIR_", "<intent-context>", "【空跑闸门", "[CONTEXT"):
        assert p in INJECTION_PREFIXES, p


# ── 正控 1（核心回归）：turn0 的 messages 尾部是 intent 注入块时，打分必须用真派单 ─
def test_extract_user_task_skips_intent_context():
    msgs = [
        {"role": "user", "content": REAL_DISPATCH},
        {"role": "user", "content": INTENT_CTX},   # ← agent_loop 在 PI 评估前追加
    ]
    picked = _extract_user_task(msgs)
    assert picked == REAL_DISPATCH[:2000], f"取到的应是真派单，实际取到 {picked[:40]!r}"
    assert _estimate_turns(picked) >= 8, "真派单必须能过阈值 8（历史因量错对象恒判 4）"


# ── 正控 2：真派单在改动后确实 ≥ min_turns ─────────────────────────────────
def test_real_dispatch_clears_est_threshold():
    assert _estimate_turns(REAL_DISPATCH) >= 8
    assert _estimate_turns(REAL_DISPATCH[:2000]) >= 8


# ── 正控 3（D2）：显式 3 checkbox + 「然后/之后」= 并行，不因依赖词被砍 ──────
def test_structured_task_is_parallel_even_with_sequence_words():
    assert estimate_parallel_elig(REAL_DISPATCH) >= 2
    assert parallel_elig_ok(REAL_DISPATCH) is True


def test_structured_demo_with_dependency_words():
    spec = """【任务】读四方讨论卡，逐条核对回执，把不一致的段落列出来，然后汇总
- [ ] 扫一遍 ~/wiki/discussions 下全部卡片
- [ ] 分别 grep 每一席的回执段落
- [ ] 汇总成对照表
之后再写结论。"""
    # 「逐」不再是依赖信号；显式结构优先
    assert estimate_parallel_elig(spec) >= 2


# ── 负控 3：无显式结构的强依赖 blob 仍必须拦（保留 K1 原意，勿放松）──────────
def test_unstructured_dependency_still_blocked():
    spec = "【任务】先做 A，然后做 B，基于 A 的结果再做 C，之后汇总"
    assert estimate_parallel_elig(spec) == 0
