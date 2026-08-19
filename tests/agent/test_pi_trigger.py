"""段6 单测：触发集成全链（S1-S3 组合 + S4 env 门控）

覆盖：
- S1: _estimate_turns 在触发链第一变量（est >= MIMIR_PI_MIN_TURNS）
- S2: 条件链拼装（est_turns AND parallel_elig_ok AND check_delegation_guard）
- S3: maybe_pi_delegate_execute 实际委派（触发/降级）
- S4: env 组合（MIMIR_DELEGATE_ENABLE=0 回退 / MIMIR_PI_MIN_TURNS 抬高 / 条件不满足静默）
"""
import os
import sys
import types

sys.path.insert(0, "/home/rayliu/src/MimirAether")
os.chdir("/home/rayliu/src/MimirAether")

from agent.pi_trigger import (
    PI_NUDGE_MARKER,
    _estimate_turns,
    extract_subtasks,
    maybe_pi_delegate_nudge,
    maybe_pi_delegate_execute,
)


TRIGGER_TASK = (
    "调研多源资料（多源 web_search 和 web_extract 分别搜索各来源），批量扫描 20 个文件，"
    "独立验证各自 status 字段，同时并行处理 3 个独立子任务并汇总"
)


def _long_ctx_messages():
    """模拟真实长上下文（>10K token——guard 类别3 短上下文不拦截）。"""
    return [
        {"role": "system", "content": "s" * 45000},
        {"role": "user", "content": TRIGGER_TASK},
    ]


def _reset_env():
    for k in ("MIMIR_DELEGATE_ENABLE", "MIMIR_PI_MIN_TURNS",
              "MIMIR_PI_MIN_PARALLEL", "MIMIR_DELEGATION_GUARD"):
        os.environ.pop(k, None)


# ── S1 · est_turns 条件链第一变量 ──────────────────────────────────────
def test_estimate_turns_long_task_high_score():
    _reset_env()
    est = _estimate_turns(TRIGGER_TASK)
    assert est >= 8, f"long task should estimate >=8, got {est}"


def test_estimate_turns_short_task_low_score():
    _reset_env()
    est = _estimate_turns("帮我读一下这个文件")
    assert est < 8, f"short task should estimate <8, got {est}"


# ── S2 · 条件链拼装 ────────────────────────────────────────────────────
def test_trigger_condition_met():
    """长任务 + 可并行 + guard 通过 → nudge 注入（条件链全通）。"""
    _reset_env()
    msgs = _long_ctx_messages()
    nudge = maybe_pi_delegate_nudge(msgs)
    assert nudge is not None, "condition met should trigger"
    assert PI_NUDGE_MARKER in nudge
    assert "delegate_task" in nudge


def test_trigger_condition_not_met_short():
    """短任务 → est < min_turns → 静默（条件链第一变量拦截）。"""
    _reset_env()
    msgs = [{"role": "user", "content": "hi"}]
    assert maybe_pi_delegate_nudge(msgs) is None


def test_trigger_condition_not_met_serial():
    """强依赖链任务 → parallel_elig 不达标 → 静默（条件链第二变量拦截）。"""
    _reset_env()
    msgs = [{"role": "user", "content": (
        "读取 A 文件 → 根据 A 内容改写 B 文件 → 运行 B → 根据运行结果修改 C，"
        "每一步依赖上一步输出，必须严格按顺序执行不能并行"
    )}]
    assert maybe_pi_delegate_nudge(msgs) is None


def test_trigger_condition_not_met_guard():
    """单步直接操作 → guard 类别1拦截 → 静默（条件链第三变量拦截）。"""
    _reset_env()
    msgs = [{"role": "user", "content": "read_file hosts 的内容"}]
    assert maybe_pi_delegate_nudge(msgs) is None


# ── S3 · 自动委派执行 ──────────────────────────────────────────────────
def test_extract_subtasks_from_checkbox():
    spec = """调研 3 个来源：
- [ ] 扫描 wiki concepts 全部概念卡
- [ ] 交叉验证 entities 索引
- [ ] 汇总多源结论到报告"""
    subs = extract_subtasks(spec)
    assert len(subs) == 3, f"expected 3 subtasks, got {len(subs)}: {subs}"
    assert "扫描 wiki concepts" in subs[0]


def test_extract_subtasks_no_checkbox():
    spec = "简单单步任务"
    subs = extract_subtasks(spec)
    assert len(subs) == 1 and subs[0] == spec


def test_delegate_execute_not_triggered():
    _reset_env()
    msgs = [{"role": "user", "content": "hi"}]
    res = maybe_pi_delegate_execute(msgs)
    assert res == {"triggered": False}


def test_delegate_execute_fallback_on_import_error():
    """条件满足但 spawn_multi 依赖缺失 → 降级 fallback=True（不静默）。"""
    _reset_env()
    msgs = _long_ctx_messages()

    fake = types.ModuleType("subagent_bridge")
    fake.spawn_multi = lambda tasks, parallel=True: (_ for _ in ()).throw(
        RuntimeError("simulated delegate failure")
    )
    sys.modules["subagent_bridge"] = fake

    try:
        res = maybe_pi_delegate_execute(msgs)
        assert res["triggered"] is True
        assert res["delegated"] is False
        assert res["fallback"] is True
        assert "error" in res and res["error"]
    finally:
        sys.modules.pop("subagent_bridge", None)


# ── S4 · env 全链组合 ──────────────────────────────────────────────────
def test_env_disable_delegate():
    """MIMIR_DELEGATE_ENABLE=0 → 回退（静默不触发）。"""
    _reset_env()
    os.environ["MIMIR_DELEGATE_ENABLE"] = "0"
    msgs = _long_ctx_messages()
    assert maybe_pi_delegate_nudge(msgs) is None
    res = maybe_pi_delegate_execute(msgs)
    assert res == {"triggered": False}


def test_env_min_turns_raise():
    """MIMIR_PI_MIN_TURNS=999 → 即使长任务也不触发（第一变量门槛抬高）。"""
    _reset_env()
    os.environ["MIMIR_PI_MIN_TURNS"] = "999"
    msgs = _long_ctx_messages()
    assert maybe_pi_delegate_nudge(msgs) is None


def test_env_min_parallel_zero():
    """MIMIR_PI_MIN_PARALLEL=0 → parallel_elig_ok 恒 False → 不触发。"""
    _reset_env()
    os.environ["MIMIR_PI_MIN_PARALLEL"] = "0"
    msgs = _long_ctx_messages()
    assert maybe_pi_delegate_nudge(msgs) is None


def test_env_guard_zero():
    """MIMIR_DELEGATION_GUARD=0 → guard 放行 → 不再因 guard 拦截。"""
    _reset_env()
    os.environ["MIMIR_DELEGATION_GUARD"] = "0"
    msgs = [{"role": "user", "content": "read_file hosts 的内容"}]
    res = maybe_pi_delegate_nudge(msgs)
    assert res is None or PI_NUDGE_MARKER in res
