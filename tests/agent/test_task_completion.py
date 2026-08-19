"""S3 测试：任务书完成度检查（四方会议 5 项清单——Loki B-L2/B-L4/B-L5 + OpenClaw 边界）——pytest 格式"""
import sys, os
sys.path.insert(0, "/home/rayliu/src/MimirAether")
os.chdir("/home/rayliu/src/MimirAether")

from agent.task_completion import check_task_completion, extract_task_spec

# 构造任务书（含子步骤清单——模仿四方卡）
TASK_SPEC = """## 任务
- [x] S1 设计
- [ ] S2 实现
- [ ] S3 测试
- [ ] S4 落盘"""


def test_no_task_spec_skips():
    """无任务书 → None（跳过）"""
    assert check_task_completion("", []) is None


def test_all_checked_passes():
    """全 [x] → None（通过）"""
    done = TASK_SPEC.replace("- [ ]", "- [x]")
    assert check_task_completion(done, []) is None


def test_unfinished_blocks():
    """有未勾项 + 无交付 → 阻断（返回理由）"""
    r = check_task_completion(TASK_SPEC, [{"role": "assistant", "content": "我完成了设计部分"}])
    assert isinstance(r, str) and "未完成" in r


def test_delivered_by_recent_assistant_passes():
    """未勾项被最近 assistant 交付（完整关键词）→ 通过（B-L4）"""
    r = check_task_completion(TASK_SPEC, [
        {"role": "assistant", "content": "S2 实现：已完成 task_completion.py 和 agent_loop 集成"},
        {"role": "assistant", "content": "S3 测试：正在写测试用例"},
        {"role": "assistant", "content": "S4 落盘：提交并更新四方卡"},
    ])
    assert r is None, f"应通过但返回: {r}"


def test_generic_string_no_false_positive():
    """B-L4 反例：泛串误判（"S2 解释"字面含 S2——不算完成）"""
    r = check_task_completion(TASK_SPEC, [
        {"role": "assistant", "content": "关于 S2 的解释：这个步骤指的是实现回调，S2 这个编号在计划里"},
    ])
    assert isinstance(r, str) and "未完成" in r, f"应阻断但返回: {r}"


def test_extract_task_spec_from_history():
    """extract_task_spec：从消息历史提取（B-L2——续作场景）"""
    messages = [
        {"role": "user", "content": "早上好"},
        {"role": "user", "content": "任务书：\n- [ ] A\n- [ ] B"},
        {"role": "assistant", "content": "收到"},
    ]
    spec = extract_task_spec(messages)
    assert "A" in spec and "B" in spec


def test_extract_task_spec_empty():
    """extract_task_spec：无任务书结构 → ''"""
    assert extract_task_spec([{"role": "user", "content": "随便聊聊"}]) == ""


def test_empty_content_skips():
    """空消息 → 跳过"""
    assert check_task_completion("", [{"role": "user", "content": ""}]) is None
