"""P0-4 接线修复（2026-09-26 · 观测第 1 步抓到的结构性零触发）。

病灶（盘上原文，`agent/agent_loop.py` P0-4 块）
  守卫 `if not getattr(self, "_parallel_read_nudge_done", False):` 在 **turn=0** 首次进入，
  此时钩子 `maybe_parallel_read_nudge(0, …)` 因 `turn < 3` **恒返 None**；
  而原实现把 `self._parallel_read_nudge_done = True` 写在 `if _pr_nudge:` **之外**
  ⇒ 标志在「什么都没注入」的那一轮就被置位
  ⇒ 此后 turn≥3 时守卫恒为假、该分支**永不进入**
  ⇒ 该钩子**结构性不可能触发**（生产证据：`hook_observations.jsonl` 有 blocked/turn_lt_3、
    无一条 injected；`agent.log` 的 `parallel-read nudge injected` = 0）。

修法：置位只在**真正注入之后**发生（少一层缩进差 = 少一次静默空转）。

测法（对齐本仓 T4 既有范式：**不复制判据代码**，从盘上真源抽块执行）
  A  真源结构       : 抽出的块里，置位语句必须嵌套在 `if _pr_nudge:` 之内
  B  行为（真块）   : 模拟 turn 序列 0→1→2→3 ⇒ 前 3 轮标志须**保持 False**，第 4 轮注入并置位
  C  负控（病形态） : 同一块把置位语句退回外层（复刻旧代码）⇒ 必须**漏注入**且第 0 轮就置位
                     （证明 B 不是恒真：检测器对旧形态有鉴别力）
  D  一次性语义     : 注入后再次进入（turn 5）不得重复注入
  E  on_task_start  : 任务开始重置（跨任务不复用旧标志）——回归
"""
from __future__ import annotations

import pathlib
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENT_LOOP = REPO_ROOT / "agent" / "agent_loop.py"

_GUARD = 'if not getattr(self, "_parallel_read_nudge_done", False):'
_FLAG = "self._parallel_read_nudge_done = True"
_MARKER = "[MIMIR_PARALLEL_READ_NUDGE]"


class _Logger:
    def __init__(self) -> None:
        self.infos: list = []

    def info(self, *a, **k):
        self.infos.append(a)


class _Self:
    def __init__(self) -> None:
        self._parallel_read_nudge_done = False
        self.task_id = "p04test0"


def _extract_block() -> str:
    """从盘上真源抽 P0-4 块（守卫行 → 置位行），去缩进。"""
    lines = AGENT_LOOP.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.strip() == _GUARD), None)
    assert start is not None, f"锚点丢失：{_GUARD!r} 不在 {AGENT_LOOP}"
    end = next((i for i, ln in enumerate(lines[start:], start)
                if ln.strip() == _FLAG), None)
    assert end is not None, f"锚点丢失：{_FLAG!r} 不在 {AGENT_LOOP}"
    block = textwrap.dedent("".join(lines[start:end + 1]))
    assert "maybe_parallel_read_nudge(turn, tool_calls_so_far)" in block, "抽到的块不调钩子——锚点漂了"
    return block


def _make_pathological(block: str) -> str:
    """受控差分件：把置位语句退回 `if _pr_nudge:` 外层（复刻修复前形态）。"""
    lines = block.splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.strip() == _FLAG)
    assert idx == len(lines) - 1, "置位语句应为块末——锚点漂了"
    # 去掉修复新增的注释行 + 把置位语句退回外层（4 空格）
    head = [ln for ln in lines[:idx] if not ln.strip().startswith("#")]
    return "\n".join(head + ["    " + _FLAG])


def _run(block: str, turns: list[tuple[int, int]], gate):
    self_obj = _Self()
    messages: list = []
    lg = _Logger()
    code = compile(block, "<agent_loop.py:p0-4-block>", "exec")
    ns = {
        "self": self_obj,
        "messages": messages,
        "maybe_parallel_read_nudge": gate,
        "logger": lg,
        "getattr": getattr,
        "turn": 0,
        "tool_calls_so_far": 0,
    }
    snapshots = []
    for t, tools in turns:
        ns["turn"] = t
        ns["tool_calls_so_far"] = tools
        exec(code, ns)
        snapshots.append((t, self_obj._parallel_read_nudge_done, len(messages)))
    return self_obj, messages, snapshots


def _real_gate(turn: int, tools: int):
    """镜像真钩子门控：turn>=3 且 tools>=2 才给文案。"""
    if turn < 3 or tools < 2:
        return None
    return _MARKER + " 提示正文"


# ------------------------------------------------------------------ 臂 A/B
_TURNS = [(0, 0), (1, 1), (2, 1), (3, 2), (5, 9)]


def test_armA_flag_assignment_nested_inside_injection_guard():
    """真源结构：置位语句必须嵌套在 `if _pr_nudge:` 之内（否则又是无条件置位）。"""
    block = _extract_block()
    lines = block.splitlines()
    idx_if = next(i for i, ln in enumerate(lines) if ln.strip() == "if _pr_nudge:")
    idx_flag = next(i for i, ln in enumerate(lines) if ln.strip() == _FLAG)
    indent_if = len(lines[idx_if]) - len(lines[idx_if].lstrip())
    indent_flag = len(lines[idx_flag]) - len(lines[idx_flag].lstrip())
    assert indent_flag > indent_if, (
        f"置位语句缩进 {indent_flag} 不大于 `if _pr_nudge:` 的 {indent_if} "
        "⇒ 又变成无条件置位（钩子将结构性零触发）"
    )


def test_armB_real_block_holds_flag_until_real_injection():
    """行为（真块）：turn 0/1/2 不得置位；turn 3 注入 + 置位；turn 5 不重复注入。"""
    self_obj, messages, snaps = _run(_extract_block(), _TURNS, _real_gate)
    holding = snaps[:3]
    for turn, flag, nmsg in holding:
        assert flag is False, f"turn {turn} 未注入却已置位 ⇒ 后续 turn>=3 永不进入（病灶复现）"
        assert nmsg == 0, f"turn {turn} 不应注入"
    assert snaps[3][1] is True and snaps[3][2] == 1, "turn 3 应注入一次并置位"
    assert snaps[4][2] == 1, "一次性语义：注入过就不再注入"
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert _MARKER in messages[0]["content"]


# -------------------------------------------------------------------- 臂 C
def test_armC_negative_control_pathological_form_misses_injection():
    """负控：复刻旧形态 ⇒ 第 0 轮即置位、turn 3 漏注入（证明臂 B 有鉴别力）。"""
    patho = _make_pathological(_extract_block())
    assert _FLAG in patho and "if _pr_nudge:" in patho
    self_obj, messages, snaps = _run(patho, _TURNS, _real_gate)
    assert snaps[0][1] is True, "病形态应在 turn 0（未注入那一轮）就置位——这是病灶本身"
    assert messages == [], "病形态在 turn 3 必须漏注入（否则本臂不成立）"
    assert snaps[3][2] == 0


def test_armC2_negative_control_is_not_a_noop_differential():
    """防「差分件其实没改」：病形态与真源必须真的不同，且差异就在置位层级。"""
    real = _extract_block()
    patho = _make_pathological(real)
    assert real != patho, "差分件与真源相同 ⇒ 臂 C 是空转负控"


# -------------------------------------------------------------------- 臂 E
def test_armE_on_task_start_resets_flag_across_tasks():
    """回归：复用同一实例执行第二个任务时，标志必须被重置（否则第二个任务收不到 nudge）。"""
    import agent.agent_loop as al

    loop = al.MimirAgentLoop(
        model_call=None,
        tool_schemas=[],
        valid_tool_names=set(),
        tool_dispatcher=None,
    )
    loop._parallel_read_nudge_done = True
    loop.on_task_start()
    assert loop._parallel_read_nudge_done is False
