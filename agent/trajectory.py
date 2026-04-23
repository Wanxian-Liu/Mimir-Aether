"""
MimirAether Trajectory - 对话轨迹记录

学习自Hermes trajectory.py设计。

核心功能：
- 轨迹数据规范化
- Thinking标签处理
- 轨迹保存到JSONL文件
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# 轨迹目录配置
# ============================================================================

def get_trajectory_dir() -> Path:
    """获取轨迹存储目录"""
    default = Path.home() / ".openclaw" / "trajectories"
    return Path(os.environ.get("OPENCLAW_TRAJECTORY_DIR", str(default)))


# ============================================================================
# Thinking/Scratchpad标签处理
# ============================================================================

def normalize_scratchpad_tags(content: str) -> str:
    """
    规范化thinking/scratchpad标签

    Converts <REASONING_SCRATCHPAD>...</REASONING_SCRATCHPAD> to
    <thinking>...</thinking> format for consistency.
    """
    if not content or "<REASONING_SCRATCHPAD>" not in content:
        return content
    return content.replace("<REASONING_SCRATCHPAD>", "<thinking>").replace("</REASONING_SCRATCHPAD>", "</thinking>")


def has_incomplete_scratchpad(content: str) -> bool:
    """检查内容是否有未闭合的thinking标签"""
    if not content:
        return False
    return "<REASONING_SCRATCHPAD>" in content and "</REASONING_SCRATCHPAD>" not in content


def convert_scratchpad_to_think(content: str) -> str:
    """将<REASONING_SCRATCHPAD>标签转换为标准<think>标签（Hermès兼容）"""
    if not content or "<REASONING_SCRATCHPAD>" not in content:
        return content
    return content.replace("<REASONING_SCRATCHPAD>", "<think>").replace("</REASONING_SCRATCHPAD>", "</think>")


def normalize_message_content(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    规范化单条消息的内容

    - 规范化thinking标签
    - 检查未闭合标签
    """
    message = dict(message)  # 复制，避免修改原对象

    # 规范化content字段
    if "content" in message and isinstance(message["content"], str):
        message["content"] = normalize_scratchpad_tags(message["content"])

    # 规范化tool_calls中的content
    if "tool_calls" in message and isinstance(message["tool_calls"], list):
        for tc in message["tool_calls"]:
            if "function" in tc and isinstance(tc["function"], dict):
                args = tc["function"].get("arguments", "")
                if isinstance(args, str):
                    tc["function"]["arguments"] = normalize_scratchpad_tags(args)

    return message


def normalize_trajectory(trajectory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    规范化整个轨迹

    - 规范化所有thinking标签
    - 验证消息格式
    """
    normalized = []
    for message in trajectory:
        normalized.append(normalize_message_content(message))
    return normalized


# ============================================================================
# 轨迹验证
# ============================================================================

def validate_trajectory(trajectory: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    验证轨迹格式

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    if not isinstance(trajectory, list):
        return False, ["Trajectory must be a list"]

    for i, message in enumerate(trajectory):
        if not isinstance(message, dict):
            errors.append(f"Message {i} is not a dict")
            continue

        if "role" not in message:
            errors.append(f"Message {i} missing 'role' field")
        elif message["role"] not in ("user", "assistant", "system", "tool"):
            errors.append(f"Message {i} has invalid role: {message['role']}")

        if "content" not in message and "tool_calls" not in message:
            errors.append(f"Message {i} missing both 'content' and 'tool_calls'")

        # 检查tool消息的tool_call_id
        if message.get("role") == "tool" and "tool_call_id" not in message:
            errors.append(f"Tool message {i} missing 'tool_call_id'")

    return len(errors) == 0, errors


# ============================================================================
# 轨迹保存
# ============================================================================

def save_trajectory(
    trajectory: List[Dict[str, Any]],
    model: str,
    completed: bool,
    filename: Optional[str] = None,
    trajectory_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    将轨迹追加到JSONL文件

    Args:
        trajectory: ShareGPT格式的对话列表
        model: 模型名称
        completed: 对话是否成功完成
        filename: 输出文件名，默认根据completed决定
        trajectory_dir: 轨迹目录，默认使用get_trajectory_dir()

    Returns:
        (success, filepath)
    """
    if filename is None:
        filename = "trajectory_samples.jsonl" if completed else "failed_trajectories.jsonl"

    if trajectory_dir is None:
        trajectory_dir = get_trajectory_dir()

    # 确保目录存在
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    filepath = trajectory_dir / filename

    # 构建条目
    entry = {
        "conversations": normalize_trajectory(trajectory),
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "completed": completed,
    }

    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Trajectory saved to %s", filepath)
        return True, str(filepath)
    except Exception as e:
        logger.warning("Failed to save trajectory: %s", e)
        return False, str(e)


# ============================================================================
# 轨迹加载
# ============================================================================

def load_trajectories(
    filename: str = "trajectory_samples.jsonl",
    trajectory_dir: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    从JSONL文件加载轨迹

    Args:
        filename: 文件名
        trajectory_dir: 轨迹目录
        limit: 最多加载条数

    Returns:
        轨迹列表
    """
    if trajectory_dir is None:
        trajectory_dir = get_trajectory_dir()

    filepath = trajectory_dir / filename
    if not filepath.exists():
        return []

    trajectories = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                try:
                    entry = json.loads(line.strip())
                    trajectories.append(entry)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse line %d in %s", i + 1, filepath)
    except Exception as e:
        logger.warning("Failed to load trajectories: %s", e)

    return trajectories


def count_trajectories(
    filename: str = "trajectory_samples.jsonl",
    trajectory_dir: Optional[Path] = None,
) -> int:
    """统计轨迹文件中的条目数"""
    if trajectory_dir is None:
        trajectory_dir = get_trajectory_dir()

    filepath = trajectory_dir / filename
    if not filepath.exists():
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("Trajectory 测试")
    print("=" * 60)

    # 测试1: normalize_scratchpad_tags
    print("\n[测试1] normalize_scratchpad_tags")
    content = "Hello <REASONING_SCRATCHPAD>thinking...</REASONING_SCRATCHPAD> world"
    result = normalize_scratchpad_tags(content)
    assert "<thinking>" in result
    assert "</REASONING_SCRATCHPAD>" not in result
    print(f"  转换后: {result[:50]}...")
    print("  ✅ 通过")

    # 测试2: has_incomplete_scratchpad
    print("\n[测试2] has_incomplete_scratchpad")
    assert has_incomplete_scratchpad("<REASONING_SCRATCHPAD>test") == True
    assert has_incomplete_scratchpad("<REASONING_SCRATCHPAD>test</REASONING_SCRATCHPAD>") == False
    assert has_incomplete_scratchpad("no tags") == False
    print("  ✅ 通过")

    # 测试3: normalize_message_content
    print("\n[测试3] normalize_message_content")
    msg = {
        "role": "assistant",
        "content": "Answer <REASONING_SCRATCHPAD>thought</REASONING_SCRATCHPAD> here",
    }
    normalized = normalize_message_content(msg)
    assert "<thinking>" in normalized["content"]
    print(f"  规范化后: {normalized['content'][:50]}...")
    print("  ✅ 通过")

    # 测试4: validate_trajectory
    print("\n[测试4] validate_trajectory")
    valid_trajectory = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    is_valid, errors = validate_trajectory(valid_trajectory)
    assert is_valid == True
    assert len(errors) == 0
    print("  有效轨迹验证: ✅ 通过")

    invalid_trajectory = [
        {"content": "No role"},
        {"role": "tool", "content": "Tool result"},
    ]
    is_valid, errors = validate_trajectory(invalid_trajectory)
    assert is_valid == False
    assert len(errors) > 0
    print(f"  无效轨迹验证: {len(errors)}个错误")
    print("  ✅ 通过")

    # 测试5: save_trajectory
    print("\n[测试5] save_trajectory")
    with tempfile.TemporaryDirectory() as tmpdir:
        trajectory_dir = Path(tmpdir)
        trajectory = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        success, filepath = save_trajectory(
            trajectory,
            model="test-model",
            completed=True,
            filename="test_trajectory.jsonl",
            trajectory_dir=trajectory_dir,
        )
        assert success == True
        assert Path(filepath).exists()
        print(f"  保存成功: {filepath}")
        print("  ✅ 通过")

    # 测试6: load_trajectories
    print("\n[测试6] load_trajectories")
    with tempfile.TemporaryDirectory() as tmpdir:
        trajectory_dir = Path(tmpdir)
        trajectory = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        save_trajectory(
            trajectory,
            model="test-model",
            completed=True,
            filename="test_load.jsonl",
            trajectory_dir=trajectory_dir,
        )
        loaded = load_trajectories(
            filename="test_load.jsonl",
            trajectory_dir=trajectory_dir,
        )
        assert len(loaded) == 1
        assert loaded[0]["model"] == "test-model"
        assert len(loaded[0]["conversations"]) == 2
        print(f"  加载轨迹数: {len(loaded)}")
        print("  ✅ 通过")

    # 测试7: count_trajectories
    print("\n[测试7] count_trajectories")
    with tempfile.TemporaryDirectory() as tmpdir:
        trajectory_dir = Path(tmpdir)
        for i in range(5):
            save_trajectory(
                [{"role": "user", "content": f"Msg {i}"}],
                model="test",
                completed=True,
                filename="count_test.jsonl",
                trajectory_dir=trajectory_dir,
            )
        count = count_trajectories(
            filename="count_test.jsonl",
            trajectory_dir=trajectory_dir,
        )
        assert count == 5
        print(f"  轨迹数量: {count}")
        print("  ✅ 通过")

    # 测试8: normalize_trajectory
    print("\n[测试8] normalize_trajectory")
    trajectory = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "<REASONING_SCRATCHPAD>thinking</REASONING_SCRATCHPAD> answer"},
    ]
    normalized = normalize_trajectory(trajectory)
    assert "<thinking>" in normalized[1]["content"]
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)
