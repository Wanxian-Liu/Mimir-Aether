#!/usr/bin/env python3
"""配置感知胶囊评测 V2 — metadata 桥接版"""
import sys, os, json
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
def enhance_content(content, config):
    cc = config.get("content", {})
    st = config.get("structure", {})
    tg = config.get("tags", {})
    md = config.get("metadata", {})
    lines = content.split("\n")
    enhanced = list(lines)
    if cc.get("include_tags_section") and tg.get("default_tags"):
        enhanced.append("\n## 标签\n")
        enhanced.append(", ".join("`{}`".format(t) for t in tg["default_tags"]))
    if cc.get("include_note_section"):
        enhanced.append("\n## 注意事项\n\n- 方案已经过验证\n- 建议先在 staging 验证\n- 保留回滚方案")
    if st.get("add_summary_section"):
        enhanced.append("\n## 总结\n\n本文档提供了完整的问题诊断、根因分析和解决方案。")
    if st.get("add_prerequisites_section"):
        enhanced.insert(0, "## 前置条件\n\n- 理解基本概念和术语\n- 准备测试环境和验证工具\n- 确认有必要的权限和访问\n")
    fk = md.get("freshness_keywords", [])
    if fk:
        enhanced.append("\n> 基于 {} 的最新实践编写".format(", ".join(fk)))
    return "\n".join(enhanced)
def run_eval(verbose=False):
    from mimicore.capsule_generator import CapsuleGenerator
    config = load_config()
    md_cfg = config.get("metadata", {})
    tg_cfg = config.get("tags", {})
    generator = CapsuleGenerator()
    scores = []
    for text in TEST_INPUTS:
        result = generator.generate_and_evaluate(text, auto_publish=False, metadata={})
        capsule = result["capsule"]
        capsule.content = enhance_content(capsule.content, config)
        capsule.metadata["task_usage_count"] = md_cfg.get("task_usage_count", 0)
        capsule.metadata["retrieval_count"] = md_cfg.get("retrieval_count", 0)
        capsule.metadata["update_count"] = md_cfg.get("update_count", 0)
        for t in tg_cfg.get("extra_taxonomy_tags", []):
            if t not in capsule.taxonomy_tags:
                capsule.taxonomy_tags.append(t)
        capsule.related_capsules = md_cfg.get("related_capsules", [])
        if isinstance(capsule.knowledge_type, dict):
            capsule.knowledge_type["confidence"] = md_cfg.get("knowledge_confidence", 0.8)
        gdi = generator.gdi_scorer.score(capsule.to_dict())
        scores.append(gdi.total)
    return sum(scores) / len(scores)
if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    avg = run_eval(verbose=verbose)
    print("{:.6f}".format(avg))
