"""段2 单测：parallel_eligibility（三信号 + 依赖过滤 + env 回退）"""
import sys, os
sys.path.insert(0, "/home/rayliu/src/MimirAether")
os.chdir("/home/rayliu/src/MimirAether")

from agent.parallel_eligibility import estimate_parallel_elig, parallel_elig_ok


def test_multi_source():
    """信号①：多源调用（2+ URL）"""
    spec = "【任务】调研 Agent 架构：web_search 查 https://a.com 和 https://b.com 两个来源对比"
    assert estimate_parallel_elig(spec) >= 1


def test_batch():
    """信号②：批量（多文件同模式）"""
    spec = "【任务】批量验证：对多个文件执行同模式 grep 检查（批量处理）"
    assert estimate_parallel_elig(spec) >= 1


def test_independent_subtasks():
    """信号③：独立子任务（- [ ] 清单 ≥3 项）"""
    spec = """【任务】完成以下步骤
- [ ] 读 A
- [ ] 读 B
- [ ] 读 C
- [ ] 汇总"""
    assert estimate_parallel_elig(spec) >= 1


def test_dependency_filter():
    """依赖反向过滤：强依赖链 → 0（不委派）"""
    spec = "【任务】先做 A，然后做 B，基于 A 的结果再做 C，之后汇总"
    assert estimate_parallel_elig(spec) == 0


def test_no_signal():
    """无信号 → 0"""
    assert estimate_parallel_elig("【任务】读一下文件 X") == 0


def test_empty():
    assert estimate_parallel_elig("") == 0


def test_env_zero_off():
    """env=0 → 回退（恒 False）"""
    os.environ["MIMIR_PI_MIN_PARALLEL"] = "0"
    try:
        assert parallel_elig_ok("【任务】调研多源 https://a.com https://b.com 批量处理") is False
    finally:
        del os.environ["MIMIR_PI_MIN_PARALLEL"]


def test_ok_threshold():
    """默认阈值 2：三信号满足 2 个 → True"""
    spec = "【任务】多源调研 https://a.com 和 https://b.com，批量处理多个文件（批量）"
    assert parallel_elig_ok(spec) is True
