"""
MimirAether Prompt Caching

两条策略：
* ``system_and_3`` (默认): 4断点 — system + 最近3条非system，同TTL
* ``prefix_and_2`` (Claude跨会话): 4断点分两档 — 稳定前缀块[0](1h) + 最后2条(5m)
  + tools[-1](1h)。新session的stable层字节不变 → 0.1x费率命中。

设计源于对Anthropic Prompt Caching协议的理解，非复制Hermes实现。
"""

import copy
from typing import Any, Dict, List, Optional


# ============================================================================
# 缓存控制
# ============================================================================

def _apply_cache_marker(
    msg: dict,
    cache_marker: dict,
    native_anthropic: bool = False,
) -> None:
    """
    为单条消息添加cache_control
    
    处理各种格式变体
    """
    role = msg.get("role", "")
    content = msg.get("content")
    
    # tool角色
    if role == "tool":
        if native_anthropic:
            msg["cache_control"] = cache_marker
        return
    
    # 空内容
    if content is None or content == "":
        msg["cache_control"] = cache_marker
        return
    
    # 字符串内容 -> 转换为列表格式
    if isinstance(content, str):
        msg["content"] = [
            {"type": "text", "text": content, "cache_control": cache_marker}
        ]
        return
    
    # 列表内容 -> 在最后一个元素上添加cache_control
    if isinstance(content, list) and content:
        last = content[-1]
        if isinstance(last, dict):
            last["cache_control"] = cache_marker


def apply_anthropic_cache_control(
    api_messages: List[Dict[str, Any]],
    cache_ttl: str = "5m",
    native_anthropic: bool = False,
) -> List[Dict[str, Any]]:
    """
    应用 system_and_3 缓存策略到消息列表
    
    最多放置4个缓存断点：
    1. 系统提示（稳定不变）
    2-4. 最近3条非系统消息（滚动窗口）
    
    Args:
        api_messages: 消息列表
        cache_ttl: 缓存TTL ("5m", "1h")
        native_anthropic: 是否使用原生Anthropic格式
        
    Returns:
        添加了cache_control断点的消息副本
    """
    messages = copy.deepcopy(api_messages)
    if not messages:
        return messages
    
    # 创建缓存标记
    marker = _build_marker(cache_ttl)
    
    breakpoints_used = 0
    
    # 系统消息 - 总是缓存
    if messages[0].get("role") == "system":
        _apply_cache_marker(messages[0], marker, native_anthropic=native_anthropic)
        breakpoints_used += 1
    
    # 最近N条非系统消息
    remaining = 4 - breakpoints_used
    non_sys_indices = [
        i for i in range(len(messages))
        if messages[i].get("role") != "system"
    ]
    for idx in non_sys_indices[-remaining:]:
        _apply_cache_marker(messages[idx], marker, native_anthropic=native_anthropic)
    
    return messages


# ============================================================================
# prefix_and_2 跨会话缓存策略
# ============================================================================

def _build_marker(ttl: str):
    """构建 cache_control marker: {"type":"ephemeral"} + 可选ttl"""
    marker = {"type": "ephemeral"}
    if ttl == "1h":
        marker["ttl"] = "1h"
    return marker


def _mark_system_stable_block(
    messages: List[Dict[str, Any]],
    long_marker: dict,
) -> bool:
    """标记system消息的第0块内容为跨会话稳定前缀（1h TTL）。
    
    调用方需先将system消息拆为多block列表：block[0]=稳定前缀，
    后续block=每会话变化的上下文+易变内容。
    
    若system消息仍是字符串（未拆分），自动包裹为单block并标记，
    此时缓存收益降低但行为正确。
    
    Returns: 是否成功放置了标记
    """
    if not messages or messages[0].get("role") != "system":
        return False
    
    sys_msg = messages[0]
    content = sys_msg.get("content")
    
    # 已是列表 → 标记第0个block
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            first["cache_control"] = long_marker
            return True
        return False
    
    # 字符串 → 包裹为单block
    if isinstance(content, str) and content:
        sys_msg["content"] = [
            {"type": "text", "text": content, "cache_control": long_marker}
        ]
        return True
    
    return False


def apply_prefix_cache(
    api_messages: List[Dict[str, Any]],
    long_ttl: str = "1h",
    rolling_ttl: str = "5m",
    native_anthropic: bool = False,
) -> List[Dict[str, Any]]:
    """prefix_and_2 缓存策略：稳定前缀1h + 最后2条消息5m。
    
    4个断点预算分配：
    - 1个：system消息block[0]（long_ttl，跨会话命中）
    - 0-2个：最后N条非system消息（rolling_ttl，会话内滚动）
    - 1个由调用方保留给 tools[-1]（见 mark_tools_for_prefix_cache）
    
    要求：调用方已将system消息按 stable/context/volatile 拆为多block列表。
    
    Args:
        api_messages: 已组装的API消息列表
        long_ttl: 稳定前缀TTL（默认1h）
        rolling_ttl: 滚动窗口TTL（默认5m）
        native_anthropic: 是否原生Anthropic API格式
    
    Returns:
        注入cache_control断点后的消息深拷贝
    """
    messages = copy.deepcopy(api_messages)
    if not messages:
        return messages
    
    long_marker = _build_marker(long_ttl)
    rolling_marker = _build_marker(rolling_ttl)
    
    placed_prefix = _mark_system_stable_block(messages, long_marker)
    
    # 滚动预算：稳定前缀占1个，留给tools[-1]1个 → 消息用剩余2个
    rolling_budget = 2 if placed_prefix else 3
    non_sys = [
        i for i in range(len(messages))
        if messages[i].get("role") != "system"
    ]
    for idx in non_sys[-rolling_budget:]:
        _apply_cache_marker(messages[idx], rolling_marker, native_anthropic=native_anthropic)
    
    return messages


def mark_tools_for_prefix_cache(
    tools: Optional[List[Dict[str, Any]]],
    long_ttl: str = "1h",
) -> Optional[List[Dict[str, Any]]]:
    """在tools列表的最后一项上放置cache_control（long_ttl）。
    
    Anthropic prefix-cache顺序: tools → system → messages。
    标记最后一个tool即缓存整个tools数组，跨会话命中。
    
    Returns: 标记后的tools深拷贝，或None/空列表时返回原值
    """
    if not tools:
        return tools
    out = copy.deepcopy(tools)
    last = out[-1]
    if isinstance(last, dict):
        last["cache_control"] = _build_marker(long_ttl)
    return out


# ============================================================================
# 成本估算
# ============================================================================

def estimate_caching_savings(
    messages: List[Dict[str, Any]],
    cache_cost_per_token: float = 0.00001,
    uncached_cost_per_token: float = 0.00003,
) -> Dict[str, Any]:
    """
    估算使用prompt caching可以节省的成本
    
    Args:
        messages: 消息列表
        cache_cost_per_token: 缓存token单价
        uncached_cost_per_token: 非缓存token单价
        
    Returns:
        包含节省估算的字典
    """
    total_input_tokens = 0
    
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            # 粗略估算：每4个字符约1个token
            total_input_tokens += len(content) // 4
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    total_input_tokens += len(text) // 4
    
    # 假设75%的token可以被缓存
    cached_tokens = int(total_input_tokens * 0.75)
    uncached_tokens = total_input_tokens - cached_tokens
    
    # 计算成本
    cached_cost = cached_tokens * cache_cost_per_token
    uncached_cost = total_input_tokens * uncached_cost_per_token
    
    savings = uncached_cost - cached_cost
    savings_pct = (savings / uncached_cost * 100) if uncached_cost > 0 else 0
    
    return {
        "total_input_tokens": total_input_tokens,
        "cached_tokens": cached_tokens,
        "uncached_tokens": uncached_tokens,
        "cached_cost": cached_cost,
        "uncached_cost": uncached_cost,
        "savings": savings,
        "savings_pct": savings_pct,
    }


def calculate_caching_benefit(
    messages: List[Dict[str, Any]],
    min_savings_threshold: float = 0.01,
) -> bool:
    """
    判断当前对话是否值得使用缓存
    
    Args:
        messages: 消息列表
        min_savings_threshold: 最小节省阈值（美元）
        
    Returns:
        是否应该启用缓存
    """
    if len(messages) < 4:
        # 对话太短，缓存收益不大
        return False
    
    savings = estimate_caching_savings(messages)
    return savings.get("savings", 0) >= min_savings_threshold


# ============================================================================
# OpenAI缓存支持（cache_max_tokens）
# ============================================================================

def apply_openai_cache(
    messages: List[Dict[str, Any]],
    max_tokens: int = 32768,
) -> List[Dict[str, Any]]:
    """
    为OpenAI消息添加缓存支持
    
    OpenAI使用 cache_max_tokens 参数来预留缓存token
    """
    messages = copy.deepcopy(messages)
    
    # 在最后一条用户消息前添加缓存提示
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "user":
            # 在这条用户消息上设置cache_max_tokens
            content = msg.get("content", "")
            if isinstance(content, str):
                msg["content"] = [
                    {"type": "text", "text": content}
                ]
            if isinstance(msg.get("content"), list):
                msg["cache_control"] = {"type": "ephemeral", "max_tokens": max_tokens}
            break
    
    return messages


# ============================================================================
# 缓存预算管理
# ============================================================================

class CacheBudgetManager:
    """
    缓存预算管理器
    
    控制缓存token的使用，避免超过模型的缓存限制
    """
    
    def __init__(
        self,
        max_cache_tokens: int = 32768,
        reserve_tokens: int = 4096,
    ):
        """
        Args:
            max_cache_tokens: 最大缓存token数
            reserve_tokens: 保留token数（用于最新回复）
        """
        self.max_cache_tokens = max_cache_tokens
        self.reserve_tokens = reserve_tokens
    
    def calculate_cache_budget(self, total_tokens: int) -> int:
        """
        计算应该缓存多少token
        
        Args:
            total_tokens: 当前总token数
            
        Returns:
            建议缓存的token数
        """
        available = self.max_cache_tokens - self.reserve_tokens
        return min(total_tokens, available)
    
    def should_use_cache(
        self,
        current_tokens: int,
        cached_tokens: int = 0,
    ) -> bool:
        """
        判断是否应该使用缓存
        
        Args:
            current_tokens: 当前输入token数
            cached_tokens: 已经缓存的token数
            
        Returns:
            是否应该使用缓存
        """
        if current_tokens <= 0:
            return False
        
        # 如果已经缓存了大部分，不再继续添加
        if cached_tokens >= self.max_cache_tokens * 0.8:
            return False
        
        # 如果输入太长，缓存收益大
        if current_tokens >= self.max_cache_tokens * 0.5:
            return True
        
        return False


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Prompt Caching 测试")
    print("=" * 60)
    
    # 测试1: Anthropic缓存控制
    print("\n[测试1] Anthropic缓存控制")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thanks!"},
        {"role": "user", "content": "Tell me about AI."},
        {"role": "assistant", "content": "AI stands for Artificial Intelligence..."},
    ]
    cached = apply_anthropic_cache_control(messages)
    print(f"  原始消息数: {len(messages)}")
    print(f"  缓存消息数: {len(cached)}")
    # 检查cache_control位置：在content[0]里
    has_cache = False
    if isinstance(cached[0].get('content'), list):
        has_cache = 'cache_control' in cached[0]['content'][0]
    print(f"  第1条有cache_control: {has_cache}")
    assert has_cache, "系统消息应该有cache_control"
    print("  ✅ 通过")
    
    # 测试2: 成本估算
    print("\n[测试2] 成本估算")
    savings = estimate_caching_savings(messages)
    print(f"  总input tokens: {savings['total_input_tokens']}")
    print(f"  可缓存tokens: {savings['cached_tokens']}")
    print(f"  节省比例: {savings['savings_pct']:.1f}%")
    print(f"  估算节省: ${savings['savings']:.6f}")
    print("  ✅ 通过")
    
    # 测试3: 判断是否使用缓存
    print("\n[测试3] 判断是否使用缓存")
    short_messages = [
        {"role": "user", "content": "Hi"}
    ]
    should_cache_short = calculate_caching_benefit(short_messages)
    print(f"  短对话({len(short_messages)}条): should_cache={should_cache_short}")
    assert should_cache_short == False, "短对话不应使用缓存"
    
    # 长对话：构造足够长的内容以超过阈值
    long_content = "Hello world. " * 500  # 约5000字符
    long_messages = [
        {"role": "system", "content": long_content},
        {"role": "user", "content": long_content},
        {"role": "assistant", "content": long_content},
        {"role": "user", "content": long_content},
    ]
    should_cache_long = calculate_caching_benefit(long_messages, min_savings_threshold=0.001)
    print(f"  长对话({len(long_messages)}条，长内容): should_cache={should_cache_long}")
    assert should_cache_long == True, "长对话应使用缓存"
    print("  ✅ 通过")
    
    # 测试4: OpenAI缓存
    print("\n[测试4] OpenAI缓存")
    oai_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Tell me a story"},
    ]
    oai_cached = apply_openai_cache(oai_messages)
    print(f"  添加缓存后最后一条: {oai_cached[-1]}")
    print("  ✅ 通过")
    
    # 测试5: CacheBudgetManager
    print("\n[测试5] CacheBudgetManager")
    manager = CacheBudgetManager(max_cache_tokens=32768, reserve_tokens=4096)
    
    budget1 = manager.calculate_cache_budget(50000)
    print(f"  50000 tokens可用缓存: {budget1}")
    assert budget1 == 28672  # 32768 - 4096
    
    should1 = manager.should_use_cache(30000, 0)
    print(f"  30000 tokens, 0 cached: should_cache={should1}")
    assert should1 == True
    
    should2 = manager.should_use_cache(1000, 0)
    print(f"  1000 tokens, 0 cached: should_cache={should2}")
    assert should2 == False
    
    should3 = manager.should_use_cache(30000, 30000)
    print(f"  30000 tokens, 30000 cached: should_cache={should3}")
    assert should3 == False  # 已缓存80%以上，不再添加
    print("  ✅ 通过")
    
    # 测试6: 空消息处理
    print("\n[测试6] 空消息处理")
    empty_messages = []
    empty_result = apply_anthropic_cache_control(empty_messages)
    print(f"  空消息: {empty_result}")
    assert empty_result == []
    print("  ✅ 通过")
    
    # 测试7: 只有系统消息
    print("\n[测试7] 只有系统消息")
    sys_only = [{"role": "system", "content": "System only"}]
    sys_cached = apply_anthropic_cache_control(sys_only)
    # cache_control在content[0]里
    has_cache = False
    if isinstance(sys_cached[0].get('content'), list):
        has_cache = 'cache_control' in sys_cached[0]['content'][0]
    print(f"  有cache_control: {has_cache}")
    assert has_cache, "系统消息应该有cache_control"
    print("  ✅ 通过")
    
    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)