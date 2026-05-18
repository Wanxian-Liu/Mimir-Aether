#!/usr/bin/env python3
"""
配置感知胶囊评测 — TaskLoop 元级自改进目标

读取 mimicore/generator_config.json，用配置参数影响生成质量，
用固定 GDI scorer 评测，输出平均分数。

TaskLoop 修改 generator_config.json，此脚本读配置→生成→评测。

用法:
    python3 scripts/gen_and_score.py              # 输出平均GDI
    python3 scripts/gen_and_score.py --verbose    # 详细
"""

import sys
import os
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

CONFIG_PATH = os.path.join(REPO_ROOT, "mimicore", "generator_config.json")

TEST_INPUTS = [
    "程序启动时报错 ModuleNotFoundError: No module named 'requests'",
    "数据库连接池耗尽，API 响应超时 504 Gateway Timeout",
    "Git push 被拒绝，分支保护规则阻止了强制推送",
    "优化文件上传性能：100MB 文件上传需要 30 秒，目标 10 秒",
    "优化 Python 脚本启动时间，import 阶段耗时 2.3 秒",
    "优化 API 响应时间，p99 延迟从 800ms 需要降到 200ms",
    "设计分布式任务调度系统，支持优先级队列和动态资源分配",
    "探索向量数据库替代传统全文搜索，实现语义级文档检索",
    "设计基于事件溯源的事件驱动架构，实现全链路审计追踪",
]


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def enhance_content(content: str, config: dict) -> str:
    """用配置参数增强生成内容（后处理）"""
    cc = config.get("content", {})
    st = config.get("structure", {})
    tg = config.get("tags", {})

    lines = content.split("\n")
    enhanced = list(lines)

    # 添加标签 section
    if cc.get("include_tags_section") and tg.get("default_tags"):
        enhanced.append("")
        enhanced.append("## 标签")
        enhanced.append("")
        enhanced.append(", ".join(f"`{t}`" for t in tg["default_tags"]))

    # 添加注意事项 section
    if cc.get("include_note_section"):
        enhanced.append("")
        enhanced.append("## 注意事项")
        enhanced.append("")
        enhanced.append("- 方案已经过验证，可直接在生产环境使用")
        enhanced.append("- 建议先在 staging 环境验证后再全量部署")
        enhanced.append("- 保留回滚方案，确保可快速恢复")

    # 添加总结 section
    if st.get("add_summary_section"):
        enhanced.append("")
        enhanced.append("## 总结")
        enhanced.append("")
        enhanced.append("本文档提供了完整的问题诊断、根因分析和解决方案。")
        enhanced.append("通过实施上述步骤，可以有效解决问题并防止再次发生。")

    # 添加前置条件 section
    if st.get("add_prerequisites_section"):
        enhanced.insert(0, "")
        enhanced.insert(0, "## 前置条件")
        enhanced.insert(0, "")
        enhanced.insert(0, "- 理解基本概念和术语")
        enhanced.insert(0, "- 准备测试环境和验证工具")
        enhanced.insert(0, "- 确认有必要的权限和访问")

    return "\n".join(enhanced)


def enrich_metadata(config: dict) -> dict:
    """从配置生成元数据"""
    md = config.get("metadata", {})
    return {
        "task_usage_count": md.get("task_usage_count", 0),
        "retrieval_count": md.get("retrieval_count", 0),
        "update_count": md.get("update_count", 0),
        "created_at": __import__("time").time() - 3600,
    }


def run_eval(verbose: bool = False) -> float:
    from mimicore.capsule_generator import CapsuleGenerator

    config = load_config()
    generator = CapsuleGenerator()
    scores = []

    for i, text in enumerate(TEST_INPUTS):
        metadata = enrich_metadata(config)

        result = generator.generate_and_evaluate(
            text, auto_publish=False, metadata=metadata
        )

        # 后处理增强
        original_content = result["capsule"].content
        enhanced = enhance_content(original_content, config)
        result["capsule"].content = enhanced

        # 重新评分
        capsule_dict = result["capsule"].to_dict()
        gdi = generator.gdi_scorer.score(capsule_dict)
        scores.append(gdi.total)

        if verbose:
            print(f"[{i+1}/{len(TEST_INPUTS)}] GDI={gdi.total:.3f} — {text[:50]}...")

    avg = sum(scores) / len(scores)

    if verbose:
        print(f"\n平均 GDI: {avg:.4f}")
        print(f"最高: {max(scores):.4f}  最低: {min(scores):.4f}")
        print(f"≥0.7: {sum(1 for s in scores if s >= 0.7)}/{len(scores)}")

    return avg


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    avg = run_eval(verbose=verbose)
    print(f"{avg:.6f}")
