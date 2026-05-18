#!/usr/bin/env python3
"""
胶囊 GDI 评测脚本 — 供 TaskLoop 调用

用法:
    python3 scripts/eval_capsule_gdi.py                    # 输出平均GDI分数
    python3 scripts/eval_capsule_gdi.py --verbose          # 详细输出

stdout 末行为平均 GDI 浮点数，供 TaskLoop run_eval() 解析。
"""

import sys
import os

# 确保 mimicore 可导入
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


# 测试输入集 — 覆盖 repair / optimize / innovate 三类
TEST_INPUTS = [
    # repair 类
    "程序启动时报错 ModuleNotFoundError: No module named 'requests'，需要安装依赖并修复导入路径",
    "数据库连接池耗尽，导致 API 响应超时 504 Gateway Timeout，需要排查连接泄露",
    "Git push 被拒绝，报错 remote rejected，分支保护规则阻止了强制推送",

    # optimize 类
    "优化文件上传性能：当前 100MB 文件上传需要 30 秒，目标 10 秒以内",
    "优化 Python 脚本的启动时间，import 阶段耗时 2.3 秒需要降到 0.5 秒",
    "优化 API 响应时间，p99 延迟从 800ms 需要降到 200ms 以内",

    # innovate 类
    "设计一个分布式任务调度系统，支持优先级队列和动态资源分配",
    "探索使用向量数据库替代传统全文搜索，实现语义级文档检索",
    "设计基于事件溯源的事件驱动架构，实现全链路审计追踪",
]


def run_eval(verbose: bool = False) -> float:
    """运行评测，返回平均 GDI 分数"""
    from mimicore.capsule_generator import CapsuleGenerator

    generator = CapsuleGenerator()
    scores = []

    for i, text in enumerate(TEST_INPUTS):
        result = generator.generate_and_evaluate(text, auto_publish=False)
        gdi = result["gdi_score"].total
        scores.append(gdi)

        if verbose:
            print(f"[{i+1}/{len(TEST_INPUTS)}] GDI={gdi:.3f} — {text[:50]}...")

    avg = sum(scores) / len(scores)

    if verbose:
        print(f"\n平均 GDI: {avg:.4f}")
        print(f"最高: {max(scores):.4f}  最低: {min(scores):.4f}")
        print(f"≥0.7: {sum(1 for s in scores if s >= 0.7)}/{len(scores)}")

    return avg


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    avg = run_eval(verbose=verbose)
    # 末行输出纯数值 — TaskLoop 解析用
    print(f"{avg:.6f}")
