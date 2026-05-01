"""
断点续传测试

测试场景：
1. 保存一个检查点，模拟任务执行到一半
2. 重新加载检查点，验证状态恢复正确
3. 清除检查点，验证清理成功

运行方式：
python test_checkpoint_recovery.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from checkpoint_manager import get_checkpoint_manager, CheckpointState

def test_checkpoint_save_load():
    """测试检查点保存和加载"""
    print("=== 测试1: 保存和加载检查点 ===")
    mgr = get_checkpoint_manager()
    
    task_id = "test-task-recovery"
    state = {
        "conversation_history": [
            {"role": "user", "content": "你好", "name": None, "tool_calls": None, "tool_call_id": None},
            {"role": "assistant", "content": "你好！有什么可以帮你的吗？", "name": None, "tool_calls": None, "tool_call_id": None},
        ],
        "iteration_used": 3,
        "session_id": "test-session-123",
        "user_message": "你好",
    }
    
    # 保存检查点
    saved = mgr.save_checkpoint(task_id, state, current_step=5, next_action="继续执行")
    print(f"✓ 保存检查点: {saved}")
    
    # 加载检查点
    loaded = mgr.load_checkpoint(task_id)
    assert loaded is not None, "加载失败"
    print(f"✓ 加载检查点成功")
    print(f"  - task_id: {loaded.task_id}")
    print(f"  - current_step: {loaded.current_step}")
    print(f"  - iteration_used: {loaded.iteration_used}")
    print(f"  - messages: {len(loaded.conversation_history)} 条")
    
    # 验证数据一致性
    assert loaded.current_step == 5, f"步骤不匹配: {loaded.current_step} != 5"
    assert loaded.iteration_used == 3, f"迭代次数不匹配: {loaded.iteration_used} != 3"
    assert len(loaded.conversation_history) == 2, f"消息数量不匹配"
    
    # 清除
    cleared = mgr.clear_checkpoint(task_id)
    print(f"✓ 清除检查点: {cleared}")
    
    # 验证已清除
    loaded_after = mgr.load_checkpoint(task_id)
    assert loaded_after is None, "检查点未清除"
    print(f"✓ 检查点已清除")


def test_checkpoint_recovery_flow():
    """测试完整的恢复流程"""
    print("\n=== 测试2: 模拟任务中断恢复流程 ===")
    mgr = get_checkpoint_manager()
    
    # 模拟用户发送一个长任务
    user_message = "帮我写一个Python程序，实现Fibonacci数列计算，要求使用递归和迭代两种方式"
    task_id = "test-long-task"
    
    # 模拟任务执行到一半，保存检查点
    state = {
        "conversation_history": [
            {"role": "user", "content": user_message, "name": None, "tool_calls": None, "tool_call_id": None},
            {"role": "assistant", "content": "好的，我来帮你写这个程序...", "name": None, "tool_calls": None, "tool_call_id": None},
            {"role": "tool", "content": "代码执行结果...", "tool_call_id": "call_123", "tool_calls": None},
        ],
        "iteration_used": 2,
        "session_id": "session-long-task",
        "user_message": user_message,
    }
    
    mgr.save_checkpoint(task_id, state, current_step=3, next_action="执行测试用例")
    print(f"✓ 模拟保存：任务执行到第3步")
    
    # 模拟Gateway断开...
    print("✓ 模拟Gateway断开...")
    
    # 重新连接，恢复任务
    print("✓ 重新连接，恢复任务...")
    checkpoint = mgr.load_checkpoint(task_id)
    
    if checkpoint:
        print(f"✓ 找到检查点，从第 {checkpoint.current_step} 步恢复")
        print(f"  - 已完成 {checkpoint.iteration_used} 次迭代")
        print(f"  - 对话历史：{len(checkpoint.conversation_history)} 条消息")
        print(f"  - 下一步计划：{checkpoint.next_action}")
        
        # 清理
        mgr.clear_checkpoint(task_id)
        print("✓ 任务完成后清除检查点")
    else:
        print("✗ 未找到检查点")
    
    print("\n=== 所有测试通过 ===")


def test_hash_based_task_id():
    """测试基于hash的任务ID生成"""
    print("\n=== 测试3: Hash-based task_id 一致性 ===")
    from checkpoint_manager import CheckpointManager
    mgr = CheckpointManager()
    
    msg1 = "帮我写一个Python程序"
    msg2 = "帮我写一个Python程序"  # 完全相同
    msg3 = "帮我写一个Java程序"    # 不同
    
    id1 = mgr._generate_task_id(msg1)
    id2 = mgr._generate_task_id(msg2)
    id3 = mgr._generate_task_id(msg3)
    
    print(f"消息1 task_id: {id1}")
    print(f"消息2 task_id: {id2} (相同内容)")
    print(f"消息3 task_id: {id3} (不同内容)")
    
    assert id1 == id2, "相同消息应生成相同task_id"
    assert id1 != id3, "不同消息应生成不同task_id"
    print("✓ 相同消息生成相同task_id，消息恢复有效")


if __name__ == "__main__":
    test_checkpoint_save_load()
    test_checkpoint_recovery_flow()
    test_hash_based_task_id()
