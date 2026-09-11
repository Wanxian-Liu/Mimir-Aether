"""档2-① gateway 卫生压缩可观测性契约测试（2026-09-11）

回归背景：9-11 12:29 卫生压缩**触发了**却既无 result 也无 failure 行——静默
无人区。根因是两个 never-logged 出口：
  · `_hyg_runtime.get("api_key")` 为假 → if 分支不执行，静默返回
  · `len(_hyg_msgs) < 4` → 同样静默返回
另外 8-15 那次 `162 → 162 msgs` 是 no-op，却打的是 "compressed" 行，会被误读成
压缩成功。

本测试锁定"触发/结果/放弃"三态各自可观测，且 no-op 不得冒充成功。
（契约测试——与 tests/gateway/test_e011_session_hygiene_bindings.py 同风格。）
"""
import os
import sys

src_dir = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, src_dir)

ROUTE_MIXIN = os.path.join(src_dir, "gateway", "router", "agent_route_mixin.py")

REQUIRED_MARKERS = [
    # 触发（含 layer 与阈值来源，便于与 agent 侧对账）
    "[COMPRESS] trigger layer=gateway",
    # 静默出口 ①：无 runtime api_key
    "reason=no_api_key",
    # 静默出口 ②：可压缩 user/assistant 消息不足
    "reason=too_few_user_assistant_msgs",
    # 结果：真压缩
    "[COMPRESS] result layer=gateway",
    # 结果：no-op（消息数未降）——不得冒充成功
    "reason=noop",
    # 异常
    "abort layer=gateway reason=exception",
]


def _source() -> str:
    with open(ROUTE_MIXIN, encoding="utf-8") as fh:
        return fh.read()


def test_all_compress_markers_present():
    src = _source()
    missing = [m for m in REQUIRED_MARKERS if m not in src]
    assert not missing, f"gateway 卫生压缩缺少可观测性标记: {missing}"


def test_noop_branch_precedes_success_branch():
    """no-op 判定必须在 result 成功行之前（否则 no-op 会被记为压缩成功）。"""
    src = _source()
    i_noop = src.index("reason=noop")
    i_result = src.index("[COMPRESS] result layer=gateway")
    assert i_noop < i_result, "no-op 分支顺序错误：可能把 no-op 记为成功"


def test_skip_branches_are_logged_not_silent():
    """两个静默出口必须各有 warning 日志（此前无任何输出）。"""
    src = _source()
    for marker, branch in (
        ("reason=no_api_key", 'if not _hyg_runtime.get("api_key")'),
        ("reason=too_few_user_assistant_msgs", "if len(_hyg_msgs) < 4"),
    ):
        assert branch in src, f"缺少补日志的分支: {branch}"
        i_branch = src.index(branch)
        # 日志应紧邻该分支（其后 500 字符内出现 marker）
        assert marker in src[i_branch : i_branch + 700], (
            f"分支 {branch} 未紧跟日志 {marker}（仍是静默出口）"
        )


def test_result_line_keeps_backward_compatible_session_hygiene_line():
    """保留原 'Session hygiene: compressed' 行（既有 grep/文档依赖），不回归。"""
    src = _source()
    assert "Session hygiene: compressed %s → %s msgs" in src
    assert "Session hygiene auto-compress failed: %s" in src
