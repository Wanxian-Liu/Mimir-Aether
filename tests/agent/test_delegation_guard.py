"""段4 单测：反向清单过滤（Loki 12 类不该委派 · 🔴 五类永拒 · 触发前置闸）

覆盖：五类各测（单步直接/高度串行依赖/短上下文<10K/写盘类commit/需审计留痕）
     + 通过场景 + env MIMIR_DELEGATION_GUARD=0 回退。
"""
import os
import sys

sys.path.insert(0, os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.delegation_guard import (
    check_delegation_guard,
    delegation_guard_enabled,
    GUARD_ENV,
    SHORT_CONTEXT_TOKEN_THRESHOLD,
)


def _unset_guard_env():
    """确保默认开（MIMIR_DELEGATION_GUARD 未设 = 开）。"""
    os.environ.pop(GUARD_ENV, None)


# ── 类别 1 · 单步直接操作 ──────────────────────────────────────────────
def test_single_step_read_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("read_file /etc/hosts")
    assert allow is False
    assert "类别1" in reason


def test_single_step_shell_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("grep -rn parallel_elig agent/")
    assert allow is False
    assert "类别1" in reason


def test_single_step_chinese_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("读一下 /path/to/config.yaml 的模型配置")
    assert allow is False
    assert "类别1" in reason


def test_single_tool_call_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("调用 terminal('git status') 一次并返回输出")
    assert allow is False
    assert "类别1" in reason


# ── 类别 2 · 高度串行依赖 ──────────────────────────────────────────────
def test_serial_chain_arrows_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("读→析→写→验 全链条")
    assert allow is False
    assert "类别2" in reason


def test_serial_chain_steps_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard(
        "先读取 A 文件，然后分析结构，接着推理结论，最后对比验证输出"
    )
    assert allow is False
    assert "类别2" in reason


def test_serial_chain_sequential_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("串行执行 5 个依赖步骤，每步基于上一步输出")
    assert allow is False
    assert "类别2" in reason


# ── 类别 3 · 短上下文（<10K token）────────────────────────────────────
def test_short_context_messages_blocked():
    _unset_guard_env()
    small_msgs = [{"content": "你好" * 500}]  # ~1000 字符 ≈ 250 token < 10K
    allow, reason = check_delegation_guard("多源调研主题 X", messages=small_msgs)
    assert allow is False
    assert "类别3" in reason


def test_short_context_self_report_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("这个任务 5 行以内就能搞定")
    assert allow is False
    assert "类别3" in reason


# ── 类别 4 · 写盘类/commit 决策 ────────────────────────────────────────
def test_disk_write_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("把调研结果写入 /tmp/report.md")
    assert allow is False
    assert "类别4" in reason


def test_commit_decision_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("完成后 git commit 并推送")
    assert allow is False
    assert "类别4" in reason


def test_luopan_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("把结论落盘到 wiki/concepts/ 下")
    assert allow is False
    assert "类别4" in reason


# ── 类别 5 · 需审计留痕的关键决策 ──────────────────────────────────────
def test_audit_finance_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("帮我做财务合同对外承诺的审批决策")
    assert allow is False
    assert "类别5" in reason


def test_audit_credential_blocked():
    _unset_guard_env()
    allow, reason = check_delegation_guard("读取凭证文件中的 api key: xxxx")
    assert allow is False
    assert "类别5" in reason


# ── 通过场景（🟢 默认可委派 3 类）─────────────────────────────────────
def test_pass_parallel_research():
    _unset_guard_env()
    spec = (
        "并行调研 5 个独立主题：A/B/C/D/E，每个主题用 web_search 查询多个独立来源，"
        "各自输出调研摘要后由主线程汇总"
    )
    allow, reason = check_delegation_guard(spec)
    assert allow is True
    assert "通过" in reason


def test_pass_multi_file_scan():
    _unset_guard_env()
    spec = "扫描 src/ 下所有 .py 文件，提取每个文件的 import 语句并统计引用次数"
    allow, reason = check_delegation_guard(spec)
    assert allow is True
    assert "通过" in reason


def test_pass_batch_verify():
    _unset_guard_env()
    spec = "批量验证 20 个 JSON 文件：解析 + 断言 schema 字段非空（同输入同输出）"
    allow, reason = check_delegation_guard(spec)
    assert allow is True
    assert "通过" in reason


# ── env 开关 ───────────────────────────────────────────────────────────
def test_env_zero_fallback():
    os.environ[GUARD_ENV] = "0"
    try:
        allow, reason = check_delegation_guard("write_file /tmp/x.md 内容")
        assert allow is True  # 回退：放行不拦截
        assert "回退" in reason
    finally:
        os.environ.pop(GUARD_ENV, None)


def test_env_default_on():
    _unset_guard_env()
    assert delegation_guard_enabled() is True
    allow, _ = check_delegation_guard("write_file /tmp/x.md 内容")
    assert allow is False  # 默认开——命中写盘类


def test_env_one_on():
    os.environ[GUARD_ENV] = "1"
    try:
        assert delegation_guard_enabled() is True
    finally:
        os.environ.pop(GUARD_ENV, None)


def test_threshold_constant():
    """Loki 12 类 #3：<10K token 阈值常量固化。"""
    assert SHORT_CONTEXT_TOKEN_THRESHOLD == 10_000
