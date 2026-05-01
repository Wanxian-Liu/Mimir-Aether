"""
MimirAether Memory Fencing

学习自Hermes Memory Fencing：
- <memory-context> 标签隔离
- 防止记忆内容混淆为用户输入
- 记忆边界保护
- 内容安全过滤

核心策略：
- 记忆内容必须包裹在特殊标签中
- 标签内的内容不会被解析为指令
- 防止prompt注入和记忆混淆
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# 标签定义
MEMORY_CONTEXT_OPEN = "<memory-context>"
MEMORY_CONTEXT_CLOSE = "</memory-context>"

# 嵌套标签（用于更细粒度的隔离）
MEMORY_BLOCK_OPEN = "<memory-block>"
MEMORY_BLOCK_CLOSE = "</memory-block>"

# 注入防护模式
INJECTION_PATTERNS = [
    # 指令注入
    r"(ignore\s+previous\s+instructions?)",
    r"(ignore\s+all\s+previous\s+commands?)",
    r"(disregard\s+your\s+instructions?)",
    r"(you\s+are\s+now\s+)",
    r"(system\s+prompt\s+leak)",
    r"(reveal\s+your\s+system\s+prompt)",
    r"(forget\s+everything)",
    r"(new\s+system\s+prompt)",
    # 模板注入
    r"\{\{.*?\}\}",
    r"\$\{[^}]+\}",
    r"<%.*?%>",
    # XSS/HTML注入
    r"<script[^>]*>.*?</script>",
    r"<!--.*?-->",
    r"<iframe[^>]*>.*?</iframe>",
    # SQL注入模式
    r"('|(\\'))|(\"|(\\\"))|(;)|(\|)|(&&)",
    # Shell注入
    r"[;&|`$]",
    # Base64/编码注入（提高阈值避免误判）
    r"(?:[A-Za-z0-9+/]{4}){20,}",  # 至少80字符的Base64字符串
]


@dataclass
class FenceResult:
    """隔离结果"""
    content: str
    was_modified: bool
    removed_patterns: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MemoryBlock:
    """记忆块"""
    id: str
    content: str
    block_type: str = "default"  # default, fact, preference, skill
    source: str = "unknown"
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MemoryFencer:
    """
    记忆隔离器
    
    功能：
    - 用标签包裹记忆内容
    - 防止记忆内容被解析为指令
    - 检测和过滤注入攻击
    - 维护记忆边界
    """
    
    def __init__(
        self,
        enable_injection_protection: bool = True,
        enable_tag_wrapping: bool = True,
        strict_mode: bool = False,
    ):
        """
        初始化记忆隔离器
        
        Args:
            enable_injection_protection: 启用注入防护
            enable_tag_wrapping: 启用标签包裹
            strict_mode: 严格模式（拒绝包含注入模式的内容）
        """
        self.enable_injection_protection = enable_injection_protection
        self.enable_tag_wrapping = enable_tag_wrapping
        self.strict_mode = strict_mode
        
        # 编译注入模式
        self._injection_regex = re.compile(
            "|".join(INJECTION_PATTERNS),
            re.IGNORECASE | re.DOTALL
        )
        
        # 统计
        self._stats = {
            "total_processed": 0,
            "modified": 0,
            "rejected": 0,
            "injections_blocked": 0,
        }
    
    def fence(self, content: str, block_type: str = "default") -> FenceResult:
        """
        隔离处理内容
        
        Args:
            content: 原始内容
            block_type: 记忆块类型
            
        Returns:
            隔离结果
        """
        self._stats["total_processed"] += 1
        
        if not content:
            return FenceResult(
                content="",
                was_modified=False,
            )
        
        original_content = content
        removed_patterns = []
        warnings = []
        
        # 1. 注入防护
        if self.enable_injection_protection:
            content, removed = self._remove_injections(content)
            if removed:
                removed_patterns.extend(removed)
                warnings.append(f"Removed {len(removed)} injection pattern(s)")
                self._stats["injections_blocked"] += 1
        
        # 2. 标签包裹
        if self.enable_tag_wrapping:
            # 检查是否已经有标签
            if not self._has_memory_tags(content):
                content = self._wrap_with_tags(content, block_type)
                self._stats["modified"] += 1
        
        was_modified = content != original_content
        
        # 严格模式：警告但保留内容（不静默丢失数据）
        if self.strict_mode and removed_patterns:
            self._stats["rejected"] += 1
            warnings.append(f"Strict mode: {len(removed_patterns)} injection pattern(s) detected and sanitized")
            # 返回清理后的内容，不返回空字符串
        
        return FenceResult(
            content=content,
            was_modified=was_modified,
            removed_patterns=removed_patterns,
            warnings=warnings,
        )
    
    def _remove_injections(self, content: str) -> Tuple[str, List[str]]:
        """
        移除注入模式
        
        Args:
            content: 原始内容
            
        Returns:
            (处理后内容, 移除的模式列表)
        """
        removed = []
        
        def replace_match(match):
            removed.append(match.group(0)[:50])  # 记录前50字符
            return "[REDACTED]"
        
        cleaned = self._injection_regex.sub(replace_match, content)
        
        return cleaned, removed
    
    def _has_memory_tags(self, content: str) -> bool:
        """检查内容是否已包含记忆标签"""
        return (
            MEMORY_CONTEXT_OPEN in content
            or MEMORY_BLOCK_OPEN in content
        )
    
    def _wrap_with_tags(self, content: str, block_type: str) -> str:
        """
        用标签包裹内容
        
        Args:
            content: 原始内容
            block_type: 块类型
            
        Returns:
            包裹后的内容
        """
        return (
            f"{MEMORY_CONTEXT_OPEN}\n"
            f"{MEMORY_BLOCK_OPEN}\n"
            f"{content}\n"
            f"{MEMORY_BLOCK_CLOSE}\n"
            f"{MEMORY_CONTEXT_CLOSE}"
        )
    
    def extract_memory_content(self, text: str) -> List[str]:
        """
        从文本中提取记忆内容
        
        Args:
            text: 包含记忆标签的文本
            
        Returns:
            记忆内容列表
        """
        contents = []
        
        # 提取 memory-context 内的内容
        pattern = rf"{re.escape(MEMORY_CONTEXT_OPEN)}(.*?){re.escape(MEMORY_CONTEXT_CLOSE)}"
        for match in re.finditer(pattern, text, re.DOTALL):
            contents.append(match.group(1).strip())
        
        # 提取 memory-block 内的内容（如果没有 memory-context）
        if not contents:
            pattern = rf"{re.escape(MEMORY_BLOCK_OPEN)}(.*?){re.escape(MEMORY_BLOCK_CLOSE)}"
            for match in re.finditer(pattern, text, re.DOTALL):
                contents.append(match.group(1).strip())
        
        return contents
    
    def sanitize_for_context(
        self,
        text: str,
        max_length: int = 4000,
    ) -> str:
        """
        清理文本用于上下文
        
        确保记忆不会被误解析为指令。
        
        Args:
            text: 输入文本
            max_length: 最大长度
            
        Returns:
            清理后的文本
        """
        # 提取记忆内容
        memory_contents = self.extract_memory_content(text)
        
        if memory_contents:
            # 已有记忆标签，额外处理
            result_parts = []
            
            # 保留非记忆部分
            remaining = text
            for mc in memory_contents:
                # 移除已提取的记忆
                remaining = remaining.replace(
                    f"{MEMORY_CONTEXT_OPEN}\n{MEMORY_BLOCK_OPEN}\n{mc}\n{MEMORY_BLOCK_CLOSE}\n{MEMORY_CONTEXT_CLOSE}",
                    ""
                )
            
            if remaining.strip():
                result_parts.append(remaining.strip())
            
            # 添加处理后的记忆
            for mc in memory_contents:
                fenced = self.fence(mc)
                result_parts.append(fenced.content)
            
            result = "\n\n".join(result_parts)
        else:
            # 没有记忆标签，直接隔离
            fenced = self.fence(text)
            result = fenced.content
        
        # 截断
        if len(result) > max_length:
            result = result[:max_length] + "..."
        
        return result
    
    def create_memory_block(
        self,
        content: str,
        block_id: str,
        block_type: str = "default",
        source: str = "user",
        metadata: Optional[Dict] = None,
    ) -> MemoryBlock:
        """
        创建记忆块
        
        Args:
            content: 记忆内容
            block_id: 唯一标识
            block_type: 块类型
            source: 来源
            metadata: 元数据
            
        Returns:
            记忆块
        """
        # 隔离处理
        fenced = self.fence(content, block_type)
        
        return MemoryBlock(
            id=block_id,
            content=fenced.content,
            block_type=block_type,
            source=source,
            metadata=metadata or {},
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return dict(self._stats)
    
    def reset_stats(self):
        """重置统计"""
        self._stats = {
            "total_processed": 0,
            "modified": 0,
            "rejected": 0,
            "injections_blocked": 0,
        }


class MemoryContextBuilder:
    """
    记忆上下文构建器
    
    帮助构建安全的记忆上下文字符串。
    """
    
    def __init__(self, fencer: Optional[MemoryFencer] = None):
        self.fencer = fencer or MemoryFencer()
        self._blocks: List[MemoryBlock] = []
    
    def add_fact(self, content: str, fact_id: Optional[str] = None) -> "MemoryContextBuilder":
        """添加事实记忆"""
        block_id = fact_id or f"fact_{len(self._blocks)}"
        block = self.fencer.create_memory_block(content, block_id, "fact")
        self._blocks.append(block)
        return self
    
    def add_preference(self, content: str, pref_id: Optional[str] = None) -> "MemoryContextBuilder":
        """添加偏好记忆"""
        block_id = pref_id or f"pref_{len(self._blocks)}"
        block = self.fencer.create_memory_block(content, block_id, "preference")
        self._blocks.append(block)
        return self
    
    def add_skill(self, content: str, skill_id: Optional[str] = None) -> "MemoryContextBuilder":
        """添加技能记忆"""
        block_id = skill_id or f"skill_{len(self._blocks)}"
        block = self.fencer.create_memory_block(content, block_id, "skill")
        self._blocks.append(block)
        return self
    
    def add_custom(
        self,
        content: str,
        block_id: str,
        block_type: str = "default",
    ) -> "MemoryContextBuilder":
        """添加自定义记忆"""
        block = self.fencer.create_memory_block(content, block_id, block_type)
        self._blocks.append(block)
        return self
    
    def build(self, max_length: int = 4000) -> str:
        """
        构建上下文字符串
        
        Args:
            max_length: 最大长度
            
        Returns:
            格式化的上下文字符串
        """
        if not self._blocks:
            return ""
        
        parts = [MEMORY_CONTEXT_OPEN]
        
        for block in self._blocks:
            parts.append(f"{MEMORY_BLOCK_OPEN}")
            parts.append(f"[{block.block_type.upper()}] {block.content}")
            parts.append(f"{MEMORY_BLOCK_CLOSE}")
        
        parts.append(MEMORY_CONTEXT_CLOSE)
        
        result = "\n".join(parts)
        
        # 截断
        if len(result) > max_length:
            result = result[:max_length] + f"\n... ({len(self._blocks)} memory blocks truncated)"
        
        return result
    
    def clear(self):
        """清空所有记忆块"""
        self._blocks = []
    
    def __len__(self) -> int:
        return len(self._blocks)


# 便捷函数
def fence_content(content: str, block_type: str = "default") -> str:
    """
    快速隔离内容
    
    Args:
        content: 原始内容
        block_type: 块类型
        
    Returns:
        隔离后的内容
    """
    fencer = MemoryFencer()
    result = fencer.fence(content, block_type)
    return result.content


def safe_memory_context(memory_items: List[Dict[str, str]]) -> str:
    """
    创建安全的记忆上下文
    
    Args:
        memory_items: 记忆项列表 [{"type": "fact", "content": "..."}, ...]
        
    Returns:
        安全的上下文字符串
    """
    builder = MemoryContextBuilder()
    
    for item in memory_items:
        item_type = item.get("type", "default")
        content = item.get("content", "")
        
        if item_type == "fact":
            builder.add_fact(content)
        elif item_type == "preference":
            builder.add_preference(content)
        elif item_type == "skill":
            builder.add_skill(content)
        else:
            builder.add_custom(content, f"custom_{len(builder._blocks)}")
    
    return builder.build()


# 导出
__all__ = [
    "MemoryFencer",
    "MemoryContextBuilder",
    "MemoryBlock",
    "FenceResult",
    "MEMORY_CONTEXT_OPEN",
    "MEMORY_CONTEXT_CLOSE",
    "MEMORY_BLOCK_OPEN",
    "MEMORY_BLOCK_CLOSE",
    "fence_content",
    "safe_memory_context",
]
