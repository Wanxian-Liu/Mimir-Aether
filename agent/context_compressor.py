"""
MimirAether Context Compressor

学习自Hermes Context Compressor：
- 自动压缩长对话历史
- 保护head（系统提示）和tail（最新消息）
- 中间部分用摘要压缩
- SUMMARY_PREFIX隔离压缩区域

核心策略：
- Head：100%保留（系统提示、核心指令）
- Tail：最近N条消息保留（最新上下文）
- Middle：压缩为摘要，用SUMMARY_PREFIX标记
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# 压缩标记
SUMMARY_PREFIX = "<|summary|>"

# 默认配置
DEFAULT_TAIL_SIZE = 10  # 保留最近10条消息
DEFAULT_HEAD_PROTECT = True  # 保护head（系统消息）
MAX_MESSAGES_BEFORE_COMPRESS = 50  # 超过此数量触发压缩


@dataclass
class CompressionResult:
    """压缩结果"""
    original_count: int
    compressed_count: int
    summary: str
    preserved_head: List[Dict]
    preserved_tail: List[Dict]
    compressed_middle: List[Dict]
    compression_ratio: float  # 压缩率
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ContextCompressor:
    """
    上下文压缩器
    
    功能：
    - 自动检测需要压缩的对话
    - 保护head（系统）和tail（最新）消息
    - 中间部分压缩为摘要
    - 支持增量压缩（不丢失信息）
    """
    
    def __init__(
        self,
        tail_size: int = DEFAULT_TAIL_SIZE,
        head_protect: bool = DEFAULT_HEAD_PROTECT,
        max_before_compress: int = MAX_MESSAGES_BEFORE_COMPRESS,
        enable_incremental: bool = True,
    ):
        self.tail_size = tail_size
        self.head_protect = head_protect
        self.max_before_compress = max_before_compress
        self.enable_incremental = enable_incremental
        self._compression_history: List[CompressionResult] = []
    
    def needs_compression(self, messages: List[Dict]) -> bool:
        """判断是否需要压缩"""
        non_system = [m for m in messages if m.get("role") != "system"]
        return len(non_system) > self.max_before_compress
    
    def compress(
        self,
        messages: List[Dict],
        existing_summary: Optional[str] = None,
    ) -> Tuple[List[Dict], CompressionResult]:
        """压缩对话上下文"""
        if not messages:
            return [], CompressionResult(
                original_count=0, compressed_count=0, summary="",
                preserved_head=[], preserved_tail=[], compressed_middle=[], compression_ratio=1.0,
            )
        
        original_count = len(messages)
        head, middle, tail = self._split_messages(messages)
        compressed = []
        
        if self.head_protect:
            compressed.extend(head)
        
        if middle:
            summary_text = self._generate_incremental_summary(middle, existing_summary) if (self.enable_incremental and existing_summary) else self._generate_summary(middle)
            compressed.append({
                "role": "system",
                "content": f"{SUMMARY_PREFIX}\n{summary_text}\n{SUMMARY_PREFIX}",
                "_is_compressed": True,
            })
        
        compressed.extend(tail)
        compressed_count = len(compressed)
        compression_ratio = compressed_count / original_count if original_count > 0 else 1.0
        
        result = CompressionResult(
            original_count=original_count, compressed_count=compressed_count,
            summary=summary_text if middle else "",
            preserved_head=head, preserved_tail=tail, compressed_middle=middle,
            compression_ratio=compression_ratio,
        )
        self._compression_history.append(result)
        return compressed, result
    
    def _split_messages(self, messages: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """分割消息为head、middle、tail"""
        head = []
        non_system = []
        
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if SUMMARY_PREFIX in content:
                    continue
                head.append(msg)
            else:
                non_system.append(msg)
        
        tail = non_system[-self.tail_size:] if len(non_system) > self.tail_size else non_system
        middle = non_system[:-self.tail_size] if len(non_system) > self.tail_size else []
        
        return head, middle, tail
    
    def _generate_summary(self, messages: List[Dict]) -> str:
        """生成压缩摘要"""
        if not messages:
            return ""
        
        user_count = sum(1 for m in messages if m.get("role") == "user")
        assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
        tool_count = sum(1 for m in messages if m.get("role") == "tool")
        
        topics = self._extract_topics(messages)
        tool_usage = self._extract_tool_usage(messages)
        
        summary_parts = []
        summary_parts.append(f"[对话摘要] 共{len(messages)}条消息（用户:{user_count} 助手:{assistant_count} 工具:{tool_count}）")
        
        if topics:
            summary_parts.append(f"涉及主题: {', '.join(topics[:5])}")
        
        if tool_usage:
            summary_parts.append(f"使用工具: {', '.join(tool_usage)}")
        
        if messages:
            first_user = next((m.get("content", "")[:100] for m in messages if m.get("role") == "user"), "")
            last_user = next((m.get("content", "")[:100] for m in reversed(messages) if m.get("role") == "user"), "")
            if first_user:
                summary_parts.append(f"开始: {first_user}...")
            if last_user and last_user != first_user:
                summary_parts.append(f"最近: {last_user}...")
        
        return "\n".join(summary_parts)
    
    def _generate_incremental_summary(self, new_messages: List[Dict], existing_summary: str) -> str:
        """增量摘要"""
        if not new_messages:
            return existing_summary
        
        user_count = sum(1 for m in new_messages if m.get("role") == "user")
        tool_usage = self._extract_tool_usage(new_messages)
        topics = self._extract_topics(new_messages)
        
        incremental = []
        incremental.append(f"[增量] 新增{len(new_messages)}条消息（用户:{user_count}）")
        
        if topics:
            incremental.append(f"新主题: {', '.join(topics[:3])}")
        if tool_usage:
            incremental.append(f"新增工具: {', '.join(tool_usage)}")
        
        return existing_summary + "\n\n" + "\n".join(incremental)
    
    def _extract_topics(self, messages: List[Dict], max_topics: int = 5) -> List[str]:
        """提取对话主题"""
        STOP_WORDS = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "这个", "什么", "怎么", "如何", "为什么", "could", "would",
            "should", "can", "will", "the", "a", "an", "is", "are", "was", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "of", "to", "in",
            "for", "on", "with", "at", "by", "from", "as", "or", "and", "but", "if",
            "please", "thanks", "thank", "you", "i", "me", "my", "we", "our", "it", "its",
        }
        
        topics = []
        seen = set()
        
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{3,}', content)
                
                for word in words:
                    word_lower = word.lower()
                    if word_lower not in STOP_WORDS and word_lower not in seen:
                        topics.append(word)
                        seen.add(word_lower)
                        if len(topics) >= max_topics:
                            return topics
        
        return topics
    
    def _extract_tool_usage(self, messages: List[Dict]) -> List[str]:
        """提取工具使用记录"""
        tools = []
        seen = set()
        
        for msg in messages:
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    name = tc.get("name") or tc.get("function", {}).get("name", "")
                    if name and name not in seen:
                        tools.append(name)
                        seen.add(name)
        
        return tools
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计"""
        if not self._compression_history:
            return {"total_compressions": 0, "avg_ratio": 0.0, "total_saved": 0}
        
        total = len(self._compression_history)
        avg_ratio = sum(r.compression_ratio for r in self._compression_history) / total
        total_saved = sum(r.original_count - r.compressed_count for r in self._compression_history)
        
        return {
            "total_compressions": total,
            "avg_ratio": avg_ratio,
            "total_saved": total_saved,
            "latest": self._compression_history[-1].__dict__ if self._compression_history else None,
        }
    
    def reset_history(self):
        """重置压缩历史"""
        self._compression_history = []


def compress_conversation(
    messages: List[Dict],
    tail_size: int = DEFAULT_TAIL_SIZE,
    max_before_compress: int = MAX_MESSAGES_BEFORE_COMPRESS,
) -> Tuple[List[Dict], Dict]:
    """便捷函数：一行压缩对话"""
    compressor = ContextCompressor(tail_size=tail_size, max_before_compress=max_before_compress)
    
    if not compressor.needs_compression(messages):
        return messages, {"skipped": True}
    
    compressed, result = compressor.compress(messages)
    
    return compressed, {
        "original_count": result.original_count,
        "compressed_count": result.compressed_count,
        "compression_ratio": result.compression_ratio,
    }


__all__ = [
    "ContextCompressor",
    "CompressionResult",
    "compress_conversation",
    "SUMMARY_PREFIX",
    "DEFAULT_TAIL_SIZE",
    "MAX_MESSAGES_BEFORE_COMPRESS",
]
