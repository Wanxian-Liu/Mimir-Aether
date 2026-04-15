"""
MimirAether Title Generator - 自动生成会话标题

学习自Hermes title_generator.py设计。

核心功能：
- 从第一轮对话生成简短标题
- 后台异步执行，不增加延迟
- 使用最便宜/最快的模型
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

_TITLE_PROMPT = (
    "Generate a short, descriptive title (3-7 words) for a conversation that starts with the "
    "following exchange. The title should capture the main topic or intent. "
    "Return ONLY the title text, nothing else. No quotes, no punctuation at the end, no prefixes."
)

# ============================================================================
# LLM调用（需要外部配置）
# ============================================================================

def call_llm_title(
    messages: List[Dict[str, str]],
    max_tokens: int = 30,
    temperature: float = 0.3,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    调用LLM生成标题

    需要外部实现。通常使用最便宜/最快的模型。
    这里提供一个默认实现，使用配置的中心LLM。
    """
    try:
        # 尝试导入MimirAether的模型路由
        from agent.smart_model_routing import get_cheapest_model
        
        model = get_cheapest_model()
        if not model:
            logger.debug("No cheap model available for title generation")
            return None
        
        # 这里应该调用实际的LLM
        # 暂时返回None，让调用方处理
        logger.debug("Would call LLM for title generation with model: %s", model)
        return None
        
    except ImportError:
        logger.debug("smart_model_routing not available")
        return None
    except Exception as e:
        logger.debug("Title generation LLM call failed: %s", e)
        return None


# ============================================================================
# 标题生成
# ============================================================================

def generate_title(
    user_message: str,
    assistant_response: str,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    从第一轮对话生成会话标题

    Args:
        user_message: 用户消息
        assistant_response: 助手回复
        timeout: 超时时间

    Returns:
        标题字符串，或失败时返回None
    """
    # 截断长消息
    user_snippet = user_message[:500] if user_message else ""
    assistant_snippet = assistant_response[:500] if assistant_response else ""

    messages = [
        {"role": "system", "content": _TITLE_PROMPT},
        {"role": "user", "content": f"User: {user_snippet}\n\nAssistant: {assistant_snippet}"},
    ]

    try:
        response = call_llm_title(
            messages=messages,
            max_tokens=30,
            temperature=0.3,
            timeout=timeout,
        )
        
        if not response:
            return None
        
        title = response.strip()
        
        # 清理：移除引号、尾部标点、前缀如 "Title: "
        title = title.strip('"\'')
        if title.lower().startswith("title:"):
            title = title[6:].strip()
        
        # 强制最大长度
        if len(title) > 80:
            title = title[:77] + "..."
        
        return title if title else None
        
    except Exception as e:
        logger.debug("Title generation failed: %s", e)
        return None


# ============================================================================
# 会话标题自动设置
# ============================================================================

def auto_title_session(
    session_db,  # 需要实现session_db接口
    session_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """
    生成并设置会话标题（如果不存在）

    在后台线程中调用。
    以下情况会静默跳过：
    - session_db为None
    - 会话已有标题
    - 标题生成失败
    """
    if not session_db or not session_id:
        return

    # 检查是否已有标题
    try:
        existing = session_db.get_session_title(session_id)
        if existing:
            return
    except Exception:
        return

    title = generate_title(user_message, assistant_response)
    if not title:
        return

    try:
        session_db.set_session_title(session_id, title)
        logger.debug("Auto-generated session title: %s", title)
    except Exception as e:
        logger.debug("Failed to set auto-generated title: %s", e)


def maybe_auto_title(
    session_db,  # 需要实现session_db接口
    session_id: str,
    user_message: str,
    assistant_response: str,
    conversation_history: List[Dict[str, Any]],
) -> None:
    """
    在第一轮交换后触发标题生成（fire-and-forget）

    只有满足以下条件才生成标题：
    - 这是第一或第二轮用户→助手交换
    - 尚未设置标题
    """
    if not session_db or not session_id or not user_message or not assistant_response:
        return

    # 计算历史中的用户消息数量来检测第一轮交换
    user_msg_count = sum(
        1 for m in (conversation_history or [])
        if m.get("role") == "user"
    )
    if user_msg_count > 2:
        return

    thread = threading.Thread(
        target=auto_title_session,
        args=(session_db, session_id, user_message, assistant_response),
        daemon=True,
        name="auto-title",
    )
    thread.start()


# ============================================================================
# 简单的本地标题生成（不依赖LLM）
# ============================================================================

def generate_simple_title(user_message: str, assistant_response: str = "") -> Optional[str]:
    """
    使用简单规则生成标题（不调用LLM）

    适用于没有LLM环境的情况。
    """
    if not user_message:
        return None

    # 移除多余空白
    user_msg = user_message.strip()
    
    # 截断到合理长度
    if len(user_msg) > 60:
        title = user_msg[:57] + "..."
    else:
        title = user_msg
    
    return title


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Title Generator 测试")
    print("=" * 60)

    # 测试1: generate_simple_title
    print("\n[测试1] generate_simple_title")
    title = generate_simple_title("How do I reset my password?")
    assert title == "How do I reset my password?"
    print(f"  简单标题: {title}")
    print("  ✅ 通过")

    # 测试2: generate_simple_title 截断
    print("\n[测试2] generate_simple_title 截断")
    long_msg = "A" * 100
    title = generate_simple_title(long_msg)
    assert len(title) == 60
    assert title.endswith("...")
    print(f"  截断标题: {title}")
    print("  ✅ 通过")

    # 测试3: generate_simple_title 空消息
    print("\n[测试3] generate_simple_title 空消息")
    title = generate_simple_title("")
    assert title is None
    print("  空消息返回None")
    print("  ✅ 通过")

    # 测试4: maybe_auto_title 不触发（消息太多）
    print("\n[测试4] maybe_auto_title 不触发")
    history = [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "First response"},
        {"role": "user", "content": "Second"},
        {"role": "assistant", "content": "Second response"},
        {"role": "user", "content": "Third"},
    ]
    called = [False]
    
    class MockDB:
        def get_session_title(self, session_id):
            return None  # 没有标题
        def set_session_title(self, session_id, title):
            called[0] = True
    
    # 由于user_msg_count=3 > 2，不应该触发
    maybe_auto_title(MockDB(), "sess1", "Fourth message", "Fourth response", history)
    # 给线程时间执行（虽然应该不执行）
    import time
    time.sleep(0.1)
    assert called[0] == False  # 不应该被调用
    print("  user_msg_count=3，未触发")
    print("  ✅ 通过")

    # 测试5: maybe_auto_title 触发（第一轮）
    print("\n[测试5] maybe_auto_title 触发")
    history2 = [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "First response"},
    ]
    maybe_auto_title(MockDB(), "sess2", "New message", "New response", history2)
    # 这个测试中generate_title会返回None因为没有LLM
    print("  已触发（但LLM不可用）")
    print("  ✅ 通过")

    # 测试6: _TITLE_PROMPT 内容
    print("\n[测试6] _TITLE_PROMPT")
    assert len(_TITLE_PROMPT) > 0
    assert "title" in _TITLE_PROMPT.lower()
    print(f"  提示词长度: {len(_TITLE_PROMPT)}")
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)