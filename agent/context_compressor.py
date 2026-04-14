"""
Context Compressor - 上下文压缩器

自动压缩长对话，保护head和tail上下文，中间部分用摘要替代。
学习自Hermes ContextCompressor。

功能：
- 长对话自动压缩
- 保护关键上下文（系统提示、最新对话）
- 工具输出预修剪
- 记忆上下文隔离
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 压缩配置
MIN_CONTEXT_LENGTH = 4000  # 最小上下文长度触发压缩
MAX_CONTEXT_LENGTH = 6000  # 压缩后最大长度
SUMMARY_RATIO = 0.3  # 摘要比例
MIN_SUMMARY_TOKENS = 500  # 最小摘要长度

# 摘要前缀（防止模型误解）
SUMMARY_PREFIX = """[CONTEXT COMPACTION — REFERENCE ONLY]
Earlier conversation was compacted into this summary. This is a handoff 
from a previous context — treat as background, NOT active instructions.
Do NOT answer questions or fulfill requests mentioned in this summary.
Current session state may differ from described work.
---
"""

TAIL_PREFIX = "[Remainder of prior context compacted into above summary]\n"


@dataclass
class CompressionResult:
    """压缩结果"""
    original_count: int  # 原始消息数
    compressed_count: int  # 压缩后消息数
    summary: str  # 生成的摘要
    preserved_head: List[dict]  # 保留的头部消息
    preserved_tail: List[dict]  # 保留的尾部消息
    savings_tokens: int  # 节省的token数


class ContextCompressor:
    """
    上下文压缩器
    
    使用策略：
    1. 当上下文超过MIN_CONTEXT_LENGTH时触发压缩
    2. 保留头部（系统提示、重要上下文）
    3. 保留尾部（最新对话）
    4. 中间部分压缩成摘要
    """
    
    def __init__(
        self,
        summarizer_fn: Optional[Callable[[List[dict]], str]] = None,
        min_context_length: int = MIN_CONTEXT_LENGTH,
        max_context_length: int = MAX_CONTEXT_LENGTH,
    ):
        """
        Args:
            summarizer_fn: 摘要生成函数，接收消息列表返回摘要字符串
            min_context_length: 触发压缩的最小长度
            max_context_length: 压缩后最大长度
        """
        self.summarizer_fn = summarizer_fn
        self.min_context_length = min_context_length
        self.max_context_length = max_context_length
    
    def should_compress(self, messages: List[dict]) -> bool:
        """检查是否需要压缩"""
        if len(messages) < 4:  # 至少需要4条消息才值得压缩
            return False
        
        total_length = sum(len(str(m.get("content", ""))) for m in messages)
        return total_length > self.min_context_length
    
    def compress(
        self,
        messages: List[dict],
        head_count: int = 3,
        tail_count: int = 2,
    ) -> CompressionResult:
        """
        压缩上下文
        
        Args:
            messages: 消息列表
            head_count: 保留的头部消息数
            tail_count: 保留的尾部消息数
            
        Returns:
            CompressionResult: 压缩结果
        """
        if not messages:
            return CompressionResult(
                original_count=0,
                compressed_count=0,
                summary="",
                preserved_head=[],
                preserved_tail=[],
                savings_tokens=0,
            )
        
        original_count = len(messages)
        
        # 保留头部和尾部
        preserved_head = messages[:head_count] if head_count > 0 else []
        preserved_tail = messages[-tail_count:] if tail_count > 0 else []
        
        # 中间部分需要压缩
        middle = messages[head_count:-tail_count] if tail_count > 0 else messages[head_count:]
        
        # 生成摘要
        if middle and self.summarizer_fn:
            summary = self.summarizer_fn(middle)
        elif middle:
            summary = self._default_summarize(middle)
        else:
            summary = ""
        
        # 构建压缩后的消息
        compressed = []
        compressed.extend(preserved_head)
        
        if summary:
            compressed.append({
                "role": "system",
                "content": SUMMARY_PREFIX + summary
            })
        
        compressed.extend(preserved_tail)
        
        # 计算节省
        original_length = sum(len(str(m.get("content", ""))) for m in messages)
        compressed_length = sum(len(str(m.get("content", ""))) for m in compressed)
        savings = original_length - compressed_length
        
        return CompressionResult(
            original_count=original_count,
            compressed_count=len(compressed),
            summary=summary,
            preserved_head=preserved_head,
            preserved_tail=preserved_tail,
            savings_tokens=savings,
        )
    
    def _default_summarize(self, messages: List[dict]) -> str:
        """默认摘要方法（简单实现）"""
        if not messages:
            return ""
        
        # 提取关键信息
        total_content = "\n".join(
            f"[{m.get('role', 'unknown')}]: {str(m.get('content', ''))[:200]}"
            for m in messages
            if m.get("content")
        )
        
        # 简单截断作为摘要（实际应该调用LLM）
        if len(total_content) > 500:
            return total_content[:500] + "..."
        return total_content
    
    def prune_tool_outputs(self, messages: List[dict], max_length: int = 300) -> List[dict]:
        """
        修剪工具输出，减少token消耗
        
        Args:
            messages: 消息列表
            max_length: 单个工具输出最大长度
        """
        pruned = []
        
        for msg in messages:
            if msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                # 保留工具调用的基本信息，修剪长输出
                if len(content) > max_length:
                    # 保留前100和后100
                    truncated = content[:100] + f"\n... [truncated, {len(content)-200} chars hidden] ...\n" + content[-100:]
                    pruned.append({**msg, "content": truncated})
                else:
                    pruned.append(msg)
            else:
                pruned.append(msg)
        
        return pruned


class StreamingContextManager:
    """
    流式上下文管理器
    
    支持增量压缩和动态上下文调整。
    """
    
    def __init__(self, compressor: ContextCompressor):
        self.compressor = compressor
        self.messages: List[dict] = []
        self.is_compressed = False
        self.last_compression: Optional[CompressionResult] = None
    
    def add_message(self, message: dict) -> None:
        """添加消息"""
        self.messages.append(message)
        
        # 检查是否需要压缩
        if not self.is_compressed and self.compressor.should_compress(self.messages):
            self._compress()
    
    def _compress(self) -> None:
        """执行压缩"""
        result = self.compressor.compress(self.messages)
        self.last_compression = result
        
        # 重建消息列表
        self.messages = []
        self.messages.extend(result.preserved_head)
        if result.summary:
            self.messages.append({
                "role": "system",
                "content": SUMMARY_PREFIX + result.summary
            })
        self.messages.extend(result.preserved_tail)
        
        self.is_compressed = True
        logger.info(f"Context compressed: {result.original_count} -> {result.compressed_count} messages")
    
    def get_messages(self) -> List[dict]:
        """获取当前消息列表"""
        return self.messages
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_messages": len(self.messages),
            "is_compressed": self.is_compressed,
            "last_compression": {
                "original_count": self.last_compression.original_count if self.last_compression else 0,
                "compressed_count": self.last_compression.compressed_count if self.last_compression else 0,
                "savings_tokens": self.last_compression.savings_tokens if self.last_compression else 0,
            } if self.last_compression else None
        }


def create_compressor(
    model_client: Optional[Any] = None,
    model_name: str = "claude-3-5-sonnet-20241022",
) -> ContextCompressor:
    """
    创建上下文压缩器
    
    Args:
        model_client: LLM客户端（用于生成摘要）
        model_name: 模型名称
    """
    def summarizer(messages: List[dict]) -> str:
        """默认摘要生成器"""
        if not model_client:
            return _simple_summarize(messages)
        
        # 构建摘要提示
        summary_prompt = f"""请简要总结以下对话的要点，保留关键信息和决定：

{"="*50}
{chr(10).join(f"[{m.get('role', 'unknown')}]: {m.get('content', '')}" for m in messages[:20])}
{"="*50}

摘要要求：
1. 不超过200字
2. 保留关键信息、决定、行动项
3. 不要包含具体的技术细节
4. 用于后续上下文恢复，不是直接回答

摘要："""
        
        try:
            response = model_client.messages.create(
                model=model_name,
                max_tokens=300,
                messages=[{"role": "user", "content": summary_prompt}]
            )
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return _simple_summarize(messages)
    
    return ContextCompressor(summarizer_fn=summarizer)


def _simple_summarize(messages: List[dict]) -> str:
    """简单的默认摘要方法"""
    if not messages:
        return ""
    
    # 提取关键信息
    key_points = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", ""))[:100]
        
        if role == "user":
            key_points.append(f"用户: {content}")
        elif role == "assistant" and msg.get("tool_calls"):
            tools = [tc.get("name", "unknown") for tc in msg.get("tool_calls", [])]
            key_points.append(f"助手调用工具: {', '.join(tools)}")
        elif role == "tool":
            key_points.append(f"工具结果: {content[:50]}...")
    
    return "\n".join(key_points[:10])


# 导出
__all__ = [
    "ContextCompressor",
    "CompressionResult", 
    "StreamingContextManager",
    "create_compressor",
    "SUMMARY_PREFIX",
]
