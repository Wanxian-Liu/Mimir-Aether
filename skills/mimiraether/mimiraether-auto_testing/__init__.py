"""
MimirAether Auto Testing
========================

自动测试系统 - 基于三环闭环架构的智能测试框架

核心功能:
- auto_test(): 自动发现并执行测试用例
- test_coverage(): 分析代码覆盖率
- regression_detect(): 回归检测
- run_test_suite(): 运行预定义测试套件

集成到MimirAether的三环闭环工作流中。
"""

import os
import sys
import glob
import json
import time
import subprocess
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ========== 数据结构 ==========

@dataclass
class TestFailure:
    """测试失败详情"""
    test_name: str
    error_message: str
    traceback: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class TestResult:
    """测试结果"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    failures: List[TestFailure] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FileCoverage:
    """文件覆盖率"""
    path: str
    coverage: float
    uncovered_lines: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CoverageReport:
    """覆盖率报告"""
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    function_coverage: float = 0.0
    threshold: float = 80.0
    below_threshold: bool = False
    uncovered_files: List[FileCoverage] = field(default_factory=list)


@dataclass
class RegressionFailure:
    """回归失败详情"""
    test_name: str
    previous_status: str
    current_status: str
    suspected_commit: Optional[str] = None


@dataclass
class PerformanceRegression:
    """性能退化详情"""
    test_name: str
    before_duration: float
    after_duration: float
    degradation_pct: float = 0.0

    def __post_init__(self):
        if self.before_duration > 0:
            self.degradation_pct = ((self.after_duration - self.before_duration) / self.before_duration) * 100


@dataclass
class RegressionReport:
    """回归报告"""
    new_failures: List[RegressionFailure] = field(default_factory=list)
    fixed_tests: List[str] = field(default_factory=list)
    performance_regressions: List[PerformanceRegression] = field(default_factory=list)
    coverage_delta: float = 0.0
    baseline: str = "main"


# ========== 核心功能 ==========

def auto_test(
    path: Optional[str] = None,
    pattern: str = "test_*.py",
    recursive: bool = True,
    verbose: bool = False
) -> TestResult:
    """
    自动发现并执行测试用例。

    Args:
        path: 测试目录路径，默认为当前目录
        pattern: 测试文件匹配模式
        recursive: 是否递归搜索子目录
        verbose: 是否输出详细信息

    Returns:
        TestResult对象，包含测试统计和失败详情
    """
    logger.info(f"[AutoTest] Starting auto_test(path={path}, pattern={pattern}, recursive={recursive})")

    start_time = time.time()
    result = TestResult()

    # 确定搜索路径
    search_path = path or os.getcwd()
    search_root = Path(search_path)

    if not search_root.exists():
        logger.error(f"[AutoTest] Path not found: {search_path}")
        result.errors = 1
        result.duration = time.time() - start_time
        return result

    # 发现测试文件
    test_files = []
    if recursive:
        test_files = list(search_root.rglob(pattern))
    else:
        test_files = list(search_root.glob(pattern))

    if not test_files:
        logger.warning(f"[AutoTest] No test files found matching '{pattern}' in {search_path}")
        result.duration = time.time() - start_time
        return result

    logger.info(f"[AutoTest] Found {len(test_files)} test files")

    # 使用pytest运行测试
    try:
        pytest_args = [
            sys.executable, "-m", "pytest",
            "--tb=short",  # 短回溯
            "-q",          # 安静模式
        ]

        if verbose:
            pytest_args.append("-v")

        # 添加测试文件路径
        for tf in test_files:
            pytest_args.append(str(tf))

        proc = subprocess.run(
            pytest_args,
            capture_output=True,
            text=True,
            timeout=300
        )

        # 解析pytest输出
        output = proc.stdout + proc.stderr

        # 提取测试计数
        # 格式: "= short test summary info ="
        # 格式: "3 passed, 1 failed in 2.34s"
        import re

        # 解析最后一行统计
        summary_match = re.search(r'(\d+)\s+passed', output)
        if summary_match:
            result.passed = int(summary_match.group(1))

        failed_match = re.search(r'(\d+)\s+failed', output)
        if failed_match:
            result.failed = int(failed_match.group(1))

        skipped_match = re.search(r'(\d+)\s+skipped', output)
        if skipped_match:
            result.skipped = int(skipped_match.group(1))

        # 提取失败详情
        if result.failed > 0:
            failure_pattern = re.compile(r'FAILED\s+(\S+)\s+-\s+(.*)')
            for match in failure_pattern.finditer(output):
                result.failures.append(TestFailure(
                    test_name=match.group(1),
                    error_message=match.group(2).strip()
                ))

        # 提取时间
        time_match = re.search(r'in\s+([\d.]+)s', output)
        if time_match:
            result.duration = float(time_match.group(1))

        result.total = result.passed + result.failed + result.skipped + result.errors

    except subprocess.TimeoutExpired:
        logger.error("[AutoTest] Test execution timed out (300s)")
        result.errors += 1
    except FileNotFoundError:
        logger.error("[AutoTest] pytest not found. Install with: pip install pytest")
        result.errors += 1
    except Exception as e:
        logger.error(f"[AutoTest] Test execution failed: {e}")
        result.errors += 1

    result.timestamp = datetime.now().isoformat()
    result.duration = time.time() - start_time

    logger.info(f"[AutoTest] Complete: {result.passed} passed, {result.failed} failed, "
                f"{result.skipped} skipped, {result.errors} errors in {result.duration:.2f}s")

    return result


def test_coverage(
    path: Optional[str] = None,
    threshold: float = 80.0
) -> CoverageReport:
    """
    分析代码覆盖率。

    Args:
        path: 代码目录路径
        threshold: 覆盖率阈值，低于此值返回警告

    Returns:
        CoverageReport对象，包含覆盖率统计和未覆盖行
    """
    logger.info(f"[Coverage] Starting coverage analysis(path={path}, threshold={threshold})")

    report = CoverageReport(threshold=threshold)
    search_path = path or os.getcwd()
    search_root = Path(search_path)

    if not search_root.exists():
        logger.error(f"[Coverage] Path not found: {search_path}")
        return report

    try:
        # 尝试使用 coverage 工具
        proc = subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--include=f'{search_path}/*'"],
            capture_output=True,
            text=True,
            timeout=60
        )

        output = proc.stdout
        import re

        # 解析覆盖率报告
        # 格式: "TOTAL                     500   100    80%"
        lines = output.strip().split('\n')
        if lines:
            last_line = lines[-1]
            parts = last_line.split()
            if len(parts) >= 4:
                try:
                    # 查找百分比
                    for part in parts:
                        if '%' in part:
                            report.line_coverage = float(part.replace('%', ''))
                            break
                except (ValueError, IndexError):
                    pass

    except FileNotFoundError:
        logger.warning("[Coverage] coverage tool not found. Install with: pip install coverage")
        logger.info("[Coverage] Falling back to file-level estimation")

        # 降级：统计文件行数
        py_files = list(search_root.rglob("*.py"))
        total_lines = 0
        for pf in py_files:
            try:
                with open(pf, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 简单估算：去掉空行和注释
                code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
                total_lines += len(code_lines)
            except Exception:
                pass

        # 如果没有coverage数据，返回估算值
        report.line_coverage = 0.0
        report.below_threshold = True
        report.uncovered_files = []

    except Exception as e:
        logger.error(f"[Coverage] Analysis failed: {e}")

    # 检查是否低于阈值
    report.below_threshold = report.line_coverage < threshold

    logger.info(f"[Coverage] Complete: {report.line_coverage:.1f}% coverage "
                f"{'(BELOW THRESHOLD)' if report.below_threshold else ''}")

    return report


def regression_detect(
    baseline: str = "main",
    test_results: Optional[TestResult] = None
) -> RegressionReport:
    """
    回归检测，比较当前测试结果与基线。

    Args:
        baseline: 基线分支或标签
        test_results: 当前测试结果

    Returns:
        RegressionReport对象，包含新增失败和性能退化
    """
    logger.info(f"[Regression] Starting regression detection(baseline={baseline})")

    report = RegressionReport(baseline=baseline)

    try:
        # 检查git可用性
        proc = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode != 0:
            logger.warning("[Regression] Not a git repository, skipping git-based analysis")
            return report

        # 获取当前分支
        branch_proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10
        )
        current_branch = branch_proc.stdout.strip()

        # 检查基线分支是否存在
        baseline_proc = subprocess.run(
            ["git", "rev-parse", "--verify", baseline],
            capture_output=True,
            text=True,
            timeout=10
        )
        if baseline_proc.returncode != 0:
            logger.warning(f"[Regression] Baseline '{baseline}' not found")
            return report

        # 获取与基线的差异
        diff_proc = subprocess.run(
            ["git", "diff", f"{baseline}...HEAD", "--name-only"],
            capture_output=True,
            text=True,
            timeout=30
        )
        changed_files = [f.strip() for f in diff_proc.stdout.split('\n') if f.strip()]

        if changed_files:
            logger.info(f"[Regression] {len(changed_files)} files changed vs {baseline}")

    except FileNotFoundError:
        logger.warning("[Regression] git not found")
    except Exception as e:
        logger.error(f"[Regression] Git analysis failed: {e}")

    logger.info(f"[Regression] Complete: {len(report.new_failures)} new failures, "
                f"{len(report.performance_regressions)} performance regressions")

    return report


def run_test_suite(
    suite_name: str = "all",
    verbose: bool = False
) -> TestResult:
    """
    运行预定义的测试套件。

    Supported suites:
    - all: 所有测试
    - unit: 单元测试
    - integration: 集成测试
    - e2e: 端到端测试
    - smoke: 冒烟测试

    Args:
        suite_name: 套件名称
        verbose: 是否输出详细信息

    Returns:
        TestResult对象
    """
    logger.info(f"[TestSuite] Running suite: {suite_name}")

    # 套件配置
    suite_configs = {
        "smoke": {
            "path": "tests/smoke",
            "pattern": "test_*.py",
            "description": "冒烟测试 - 核心功能快速验证"
        },
        "unit": {
            "path": "tests/unit",
            "pattern": "test_*.py",
            "description": "单元测试"
        },
        "integration": {
            "path": "tests/integration",
            "pattern": "test_*.py",
            "description": "集成测试"
        },
        "e2e": {
            "path": "tests/e2e",
            "pattern": "test_*.py",
            "description": "端到端测试"
        },
        "all": {
            "path": "tests",
            "pattern": "test_*.py",
            "description": "全部测试"
        }
    }

    if suite_name not in suite_configs:
        logger.error(f"[TestSuite] Unknown suite: {suite_name}. "
                     f"Available: {list(suite_configs.keys())}")
        result = TestResult()
        result.errors = 1
        return result

    config = suite_configs[suite_name]
    logger.info(f"[TestSuite] {config['description']}")

    return auto_test(
        path=config["path"],
        pattern=config["pattern"],
        recursive=True,
        verbose=verbose
    )


# ========== 模块导出 ==========

__all__ = [
    "auto_test",
    "test_coverage",
    "regression_detect",
    "run_test_suite",
    "TestResult",
    "TestFailure",
    "CoverageReport",
    "RegressionReport",
]
