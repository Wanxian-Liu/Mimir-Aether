"""段 7 集成测试 · PI 自动委派端到端触发链（2026-08-20 · 块3 段7）。

角色来源：engineering-code-reviewer（wiki raw: ~/wiki/raw/agency-agents/engineering/engineering-code-reviewer.md）
核心规则引用：
  1. 覆盖重要路径的测试（🟡 Testing — Are the important paths tested?）
  2. 一次审查完整反馈（One review, complete feedback——4 场景一次覆盖）
  3. 具体不笼统（Be specific——每场景断言到返回 dict 字段级）

覆盖 4 场景（任务书要求）：
  ① 条件满足触发——完整链：任务书构造 → est_turns/parallel_elig/guard → 强制指令注入 → 自动委派 delegated=True
  ② guard 拦截——est≥8 + 可并行但命中反向清单（类别4·commit）→ 静默不触发
  ③ 委派失败降级——触发条件满足但 spawn_multi 异常 → fallback=True（回退单 agent，不静默）
  ④ env 关闭回退——MIMIR_DELEGATE_ENABLE=0 → 整链关闭（triggered=False）

运行：python3 -m pytest tests/agent/test_pi_trigger_integration.py -v
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent.pi_trigger import (  # noqa: E402
    PI_NUDGE_MARKER,
    extract_subtasks,
    maybe_pi_delegate_execute,
    maybe_pi_delegate_nudge,
)

# guard 类别3 短上下文阈值（delegation_guard.SHORT_CONTEXT_TOKEN_THRESHOLD 显示层遮罩为 ***，
# 算术探针实测 T*2=20000 确认）→ 测试需 padding ≥40000 字符（同 test_pi_trigger_force.py）
_GUARD_CTX_PAD = 50000


def _mk_messages(text: str, ctx_pad_chars: int = 0) -> list:
    """构造消息：最后一条 user 消息 = 任务书；可选 assistant 填充抬高上下文 token。"""
    msgs = [{"role": "user", "content": text}]
    if ctx_pad_chars:
        msgs.append({"role": "assistant", "content": "x" * ctx_pad_chars})
    return msgs


# ① 正向任务书：est≥8（多信号词+77 张数量词） + 三信号（多源/批量/独立 checkbox≥3）
#   + 无反向清单命中 + 无强依赖链（"分别/同时" 而非 "之后/然后/基于" 链）
TRIGGER_TASK = (
    "批量调研 OpenClaw 角色库与 delegate 工具现状，分别搜索多源资料"
    "（web_search + web_extract 多 URL），逐项审计全部 77 张 sources 页面"
    "并交叉比对、汇总输出完整报告，同时整理独立子任务清单供并行派发：\n"
    "- [ ] 调研 OpenClaw 角色库实现与 Wiki 索引\n"
    "- [ ] 验证 delegate 工具注册与调用链\n"
    "- [ ] 批量核对 sources 页面证据并输出审计摘要"
)

# ② guard 拦截任务书：est 高 + 可并行信号，但含 commit（类别4·写盘类永拒）
GUARDED_TASK = (
    "批量调研全部 77 张 sources 页面并分别验证多源资料，"
    "逐项审计每条路径证据后 git commit 汇总结果并推送"
)


# ── 场景 ① 条件满足触发（完整链）──────────────────────────────────────

def test_trigger_chain_condition_met_force_injected():
    """端到端链前半：任务书 → est≥8 + parallel_elig≥2 + guard 通过 → 强制指令注入。"""
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)
    out = maybe_pi_delegate_nudge(msgs)
    assert out is not None, "条件满足应注入强制指令（非 None）"
    assert PI_NUDGE_MARKER in out, "应保留 PI marker（注入通道标识）"
    assert "必须使用 delegate_task" in out, "应为强制指令（B-Loki-Audit-1 语义）"
    assert "禁止自行串行执行" in out, "应包含禁止串行语义"


def test_trigger_chain_subtask_extraction():
    """链中段：任务书 `- [ ]` 子步骤应被拆为 ≥3 个独立子任务（自动委派输入）。"""
    subtasks = extract_subtasks(TRIGGER_TASK)
    assert len(subtasks) >= 3, f"应拆出 ≥3 子任务，实际 {len(subtasks)}: {subtasks}"
    assert all(isinstance(s, str) and s.strip() for s in subtasks), "子任务应为非空字符串"
    assert "调研 OpenClaw 角色库实现与 Wiki 索引" in subtasks, "应保留 checkbox 行内容"


def test_trigger_chain_execute_delegates(monkeypatch):
    """端到端链后半：条件满足 → maybe_pi_delegate_execute 实际自动委派（delegated=True）。"""
    fake_results = [
        SimpleNamespace(success=True, stdout="research done", error=None),
        SimpleNamespace(success=True, stdout="verify done", error=None),
        SimpleNamespace(success=False, stdout="", error="timeout"),
    ]

    def _fake_spawn_multi(tasks, parallel=True):
        # 断言委派输入：任务书拆出的子任务被包装成 general-purpose 任务
        assert isinstance(tasks, list) and len(tasks) == 3, f"应委派 3 个子任务，实际 {len(tasks)}"
        assert all(t.get("type") == "general-purpose" for t in tasks), "子任务类型应为 general-purpose"
        assert all(t.get("prompt") for t in tasks), "每个子任务都应有 prompt"
        return fake_results

    monkeypatch.setattr("subagent_bridge.spawn_multi", _fake_spawn_multi)
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)

    result = maybe_pi_delegate_execute(msgs)
    assert result.get("triggered") is True, f"应触发，实际 {result}"
    assert result.get("delegated") is True, f"应委派成功，实际 {result}"
    assert len(result.get("subtasks", [])) == 3, "subtasks 应包含 3 个子任务"
    assert len(result.get("results", [])) == 3, "results 应与子任务一一对应"
    assert result["results"][0]["success"] is True, "结果应按顺序映射 success 字段"
    assert result["results"][2]["success"] is False, "单个子任务失败不应阻断整体委派结果"


# ── 场景 ② guard 拦截 ────────────────────────────────────────────────

def test_trigger_chain_guard_blocks_silent():
    """est≥8 + 可并行 但反向清单命中（类别4·commit 永拒）→ nudge 静默（None）。"""
    msgs = _mk_messages(GUARDED_TASK, ctx_pad_chars=_GUARD_CTX_PAD)
    assert maybe_pi_delegate_nudge(msgs) is None, "guard 拦截应静默——不注入指令"


def test_trigger_chain_guard_blocks_execute_not_triggered():
    """guard 拦截同样作用于 execute 链：triggered=False（不委派）。"""
    msgs = _mk_messages(GUARDED_TASK, ctx_pad_chars=_GUARD_CTX_PAD)
    result = maybe_pi_delegate_execute(msgs)
    assert result == {"triggered": False}, f"guard 拦截时 execute 应静默返回，实际 {result}"


# ── 场景 ③ 委派失败降级 ──────────────────────────────────────────────

def test_trigger_chain_delegate_failure_fallback(monkeypatch):
    """触发条件满足但 spawn_multi 抛异常 → fallback=True（回退单 agent，不静默）。"""
    def _boom_spawn_multi(tasks, parallel=True):
        raise RuntimeError("subagent spawn crashed: 子进程启动失败")

    monkeypatch.setattr("subagent_bridge.spawn_multi", _boom_spawn_multi)
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)

    result = maybe_pi_delegate_execute(msgs)
    assert result.get("triggered") is True, "条件满足应进入委派尝试"
    assert result.get("delegated") is False, "委派失败 delegated 应为 False"
    assert result.get("fallback") is True, "必须显式降级 fallback=True（不静默吞错）"
    assert "error" in result and result["error"], "降级必须携带错误信息供调用方决策"


def test_trigger_chain_bridge_missing_fallback(monkeypatch):
    """subagent_bridge 不可导入（依赖缺失）→ 同样降级 fallback=True。"""
    import builtins

    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if name == "subagent_bridge":
            raise ImportError("No module named 'subagent_bridge'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)

    result = maybe_pi_delegate_execute(msgs)
    assert result.get("triggered") is True
    assert result.get("delegated") is False
    assert result.get("fallback") is True, "依赖缺失必须降级而非崩溃"


# ── 场景 ④ env 关闭回退 ──────────────────────────────────────────────

def test_trigger_chain_env_disabled_nudge_silent(monkeypatch):
    """MIMIR_DELEGATE_ENABLE=0 → nudge 整链关闭（条件满足也不注入）。"""
    monkeypatch.setenv("MIMIR_DELEGATE_ENABLE", "0")
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)
    assert maybe_pi_delegate_nudge(msgs) is None, "env 关闭应静默——不注入指令"


def test_trigger_chain_env_disabled_execute_not_triggered(monkeypatch):
    """MIMIR_DELEGATE_ENABLE=0 → execute 同样回退（triggered=False，不委派）。"""
    monkeypatch.setenv("MIMIR_DELEGATE_ENABLE", "0")
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)
    result = maybe_pi_delegate_execute(msgs)
    assert result == {"triggered": False}, f"env 关闭时 execute 应静默返回，实际 {result}"


def test_trigger_chain_env_default_on(monkeypatch):
    """env 未设置 → 默认开（条件满足触发——防误关回归）。"""
    monkeypatch.delenv("MIMIR_DELEGATE_ENABLE", raising=False)
    msgs = _mk_messages(TRIGGER_TASK, ctx_pad_chars=_GUARD_CTX_PAD)
    assert maybe_pi_delegate_nudge(msgs) is not None, "env 未设置应默认开启触发"
