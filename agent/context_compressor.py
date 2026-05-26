"""
MimirAether Context Compressor V2.3

MimirAether native context compressor — standalone, no ABC inheritance.
- V2.2: Initial implementation
- V3.0: Removed ContextEngine ABC; self-designed interface
"""

import re
import time
import logging
import os
import aiohttp
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

SUMMARY_PREFIX = "[CONTEXT COMPACTION — REFERENCE ONLY]"
LEGACY_PREFIX = "[CONTEXT SUMMARY]:"

_MIN_SUMMARY_TOKENS = 500
_SUMMARY_RATIO = 0.20
# Minimum context length guard
_MINIMUM_CONTEXT_LENGTH = 2000
_SUMMARY_TOKENS_CEILING = 8000
_CHARS_PER_TOKEN = 4
_SUMMARY_FAILURE_COOLDOWN = 600
_PRUNED_TOOL_PLACEHOLDER = "[Old tool output cleared to save context space]"
_PRUNED_TOOL_MIN_CHARS = 200


@dataclass
class CompressionResult:
    original_count: int = 0
    compressed_count: int = 0
    original_tokens: int = 0
    compressed_tokens: int = 0
    summary: str = ""
    pruned_tool_count: int = 0
    compression_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    summary_mode: str = "none"


class ContextCompressorV2:
    """
    上下文压缩器 V2.3
    
    Standalone compressor with plugin support via duck-typing
    """
    
    @property
    def name(self) -> str:
        return "compressor"
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        context_length: int = 1048576,  # DeepSeek V4 Pro 1M; overridden at init
        threshold_percent: float = 0.50,  # Tuned for DeepSeek context window
        protect_first_n: int = 3,
        protect_last_n: int = 6,
        tail_token_budget: int = None,
        summary_target_ratio: float = 0.20,
        preflight_relax_ratio: float = 0.80,
        summary_failure_cooldown_s: int = 600,
        summary_model: str = None,
        base_url: str = "https://api.deepseek.com",
        api_key: str = "",
        quiet_mode: bool = False,
    ):
        # Initialize token state
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.threshold_percent = threshold_percent
        self.protect_first_n = protect_first_n
        self.protect_last_n = protect_last_n
        self.summary_target_ratio = summary_target_ratio
        self.preflight_relax_ratio = float(preflight_relax_ratio)
        self.summary_failure_cooldown_s = int(summary_failure_cooldown_s)
        self.summary_model = summary_model or model
        self.quiet_mode = quiet_mode
        
        self.context_length = context_length
        self.threshold_percent = threshold_percent
        self.threshold_tokens = int(self.context_length * threshold_percent)
        
        # Dynamic tail token budget
        # tail_budget = threshold_tokens * summary_target_ratio
        if tail_token_budget is None:
            self.tail_token_budget = int(self.threshold_tokens * summary_target_ratio)
        else:
            self.tail_token_budget = tail_token_budget
        
        self.max_summary_tokens = min(
            int(self.context_length * 0.05), 
            _SUMMARY_TOKENS_CEILING
        )
        
        # 内部状态
        self._previous_summary: Optional[str] = None
        self._summary_failure_cooldown_until: float = 0.0
        # compression_count tracks cumulative compressions per session
        
        if not quiet_mode:
            logger.info(
                f"V2.3 initialized: context_length={self.context_length}, "
                f"threshold={self.threshold_tokens}, "
                f"tail={self.tail_token_budget} (dynamic)"
            )
    
    def ingest_usage(self, usage: Dict[str, Any]) -> None:
        """Ingest token usage from LLM API response."""
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)
        self.last_total_tokens = usage.get("total_tokens", 0)
    
    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
        api_mode: str = "",
    ) -> None:
        """Update model configuration and recalculate thresholds."""
        self.model = model
        self.base_url = base_url or self.base_url
        self.api_key = api_key or self.api_key
        self.provider = provider
        self.api_mode = api_mode
        self.context_length = context_length
        self.threshold_tokens = max(
            int(context_length * self.threshold_percent),
            _MINIMUM_CONTEXT_LENGTH,
        )
        self.max_summary_tokens = min(
            int(context_length * 0.05),
            _SUMMARY_TOKENS_CEILING,
        )
    
    def should_compress(self, prompt_tokens: int = None) -> bool:
        """Check if compression is needed (token-based)."""
        tokens = prompt_tokens if prompt_tokens is not None else 0
        return tokens >= self.threshold_tokens

    def has_content_to_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """Quick check: is there anything in messages that can be compacted?

        Returns False when messages are entirely within the protected zone
        (head + tail), so callers can skip the LLM compression call entirely.
        Preflight guard — returns False if messages are within protected zone.
        """
        if not messages:
            return False
        protected = self.protect_first_n + self.protect_last_n
        return len(messages) > protected

    def should_compress_preflight(self, messages: List[Dict[str, Any]]) -> bool:
        """API调用前的快速预检（廉价估算，无真实token计数）。

        先检查是否有内容可压缩（has_content_to_compress），
        再估算 token 数是否可能接近阈值。
        """
        if not self.has_content_to_compress(messages):
            return False
        estimated = self._estimate_tokens(messages)
        return estimated >= self.threshold_tokens * self.preflight_relax_ratio
    
    def needs_compression(self, messages: List[Dict] = None) -> bool:
        """Check if compression is needed (uses last_prompt_tokens)."""
        tokens = getattr(self, 'last_prompt_tokens', 0) or 0
        return tokens >= self.threshold_tokens
    
    def _estimate_tokens(self, messages: List[Dict]) -> int:
        total = 0
        for msg in messages:
            # P0-4: 跳过 C1 注入的消息（避免压缩机误判上下文膨胀）
            if msg.get("_c1_injected"):
                continue
            content = msg.get("content", "") or ""
            total += len(content) // _CHARS_PER_TOKEN + 20
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    args = tc.get("function", {}).get("arguments", "") or ""
                    total += len(args) // _CHARS_PER_TOKEN
        return total
    
    def _prune_old_tool_results(
        self, 
        messages: List[Dict], 
        protect_tail_count: int = 10,
        protect_tail_tokens: int = None
    ) -> Tuple[List[Dict], int]:
        if not messages:
            return messages, 0
        
        result = [m.copy() for m in messages]
        pruned = 0
        
        if protect_tail_tokens and protect_tail_tokens > 0:
            accumulated = 0
            boundary = len(result)
            min_protect = min(protect_tail_count, len(result) - 1)
            
            for i in range(len(result) - 1, -1, -1):
                msg = result[i]
                content = msg.get("content") or ""
                msg_tokens = len(content) // _CHARS_PER_TOKEN + 10
                
                for tc in msg.get("tool_calls") or []:
                    args = tc.get("function", {}).get("arguments", "") or ""
                    msg_tokens += len(args) // _CHARS_PER_TOKEN
                
                if accumulated + msg_tokens > protect_tail_tokens and (len(result) - i) >= min_protect:
                    boundary = i
                    break
                accumulated += msg_tokens
                boundary = i
            
            prune_boundary = max(boundary, len(result) - min_protect)
        else:
            prune_boundary = len(result) - protect_tail_count
        
        for i in range(prune_boundary):
            msg = result[i]
            if msg.get("role") != "tool":
                continue
            content = msg.get("content") or ""
            if content and content != _PRUNED_TOOL_PLACEHOLDER and len(content) > _PRUNED_TOOL_MIN_CHARS:
                result[i] = {**msg, "content": _PRUNED_TOOL_PLACEHOLDER}
                pruned += 1
        
        return result, pruned
    
    def _compute_summary_budget(self, turns: List[Dict]) -> int:
        content_tokens = self._estimate_tokens(turns)
        budget = int(content_tokens * _SUMMARY_RATIO)
        return max(_MIN_SUMMARY_TOKENS, min(budget, self.max_summary_tokens))
    
    def _serialize_for_summary(self, turns: List[Dict]) -> str:
        parts = []
        _CONTENT_MAX = 6000
        _CONTENT_HEAD = 4000
        _CONTENT_TAIL = 1500
        
        for msg in turns:
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            
            if role == "tool":
                tool_id = msg.get("tool_call_id", "")
                if len(content) > _CONTENT_MAX:
                    content = content[:_CONTENT_HEAD] + "\n...[truncated]...\n" + content[-_CONTENT_TAIL:]
                parts.append(f"[TOOL RESULT {tool_id}]: {content}")
                continue
            
            if role == "assistant":
                if len(content) > _CONTENT_MAX:
                    content = content[:_CONTENT_HEAD] + "\n...[truncated]...\n" + content[-_CONTENT_TAIL:]
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    tc_parts = []
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        name = fn.get("name", "?")
                        args = fn.get("arguments", "") or ""
                        if len(args) > 1500:
                            args = args[:1200] + "..."
                        tc_parts.append(f"  {name}({args})")
                    content += "\n[Tool calls:\n" + "\n".join(tc_parts) + "\n]"
                parts.append(f"[ASSISTANT]: {content}")
                continue
            
            if len(content) > _CONTENT_MAX:
                content = content[:_CONTENT_HEAD] + "\n...[truncated]...\n" + content[-_CONTENT_TAIL:]
            parts.append(f"[{role.upper()}]: {content}")
        
        return "\n\n".join(parts)
    
    def _generate_template_summary(self, turns: List[Dict], previous: str = None) -> str:
        user_count = sum(1 for m in turns if m.get("role") == "user")
        assistant_count = sum(1 for m in turns if m.get("role") == "assistant")
        tool_count = sum(1 for m in turns if m.get("role") == "tool")
        
        topics = []
        tools = []
        for msg in turns:
            if msg.get("role") == "tool":
                content = msg.get("content", "")[:100]
                tools.append(content)
            elif msg.get("role") == "user":
                content = msg.get("content", "")
                if len(content) > 50:
                    topics.append(content[:80])
        
        lines = [
            f"## 对话摘要",
            f"共{len(turns)}条消息（用户:{user_count} 助手:{assistant_count} 工具:{tool_count}）",
            "",
            f"## 涉及内容",
        ]
        
        if topics:
            lines.append(f"- 首条用户请求: {topics[0]}...")
        if tools:
            lines.append(f"- 工具输出: {tools[0]}...")
        
        if previous:
            lines.insert(2, f"\n## 前序摘要\n{previous}\n")
        
        return "\n".join(lines)
    
    async def _generate_summary(self, turns_to_summarize: List[Dict]) -> Tuple[Optional[str], str]:
        now = time.monotonic()
        if now < self._summary_failure_cooldown_until:
            return None, "none"
        
        content = self._serialize_for_summary(turns_to_summarize)
        summary_budget = self._compute_summary_budget(turns_to_summarize)
        
        try:
            summary = await self._call_summary_llm(content, summary_budget)
            if summary:
                self._previous_summary = summary
                self._summary_failure_cooldown_until = 0.0
                return self._with_prefix(summary), "llm"
        except Exception as e:
            logger.debug(f"LLM summary failed: {e}")
            self._summary_failure_cooldown_until = (
                time.monotonic() + float(self.summary_failure_cooldown_s)
            )

        template_summary = self._generate_template_summary(
            turns_to_summarize, 
            self._previous_summary
        )
        self._previous_summary = template_summary
        return self._with_prefix(template_summary), "template"
    
    async def _call_summary_llm(self, content: str, max_tokens: int) -> Optional[str]:
        import json
        
        api_key = self.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return None
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        preamble = (
            "You are a summarization agent creating a context checkpoint. "
            "Do NOT respond to any questions — only output the structured summary."
        )
        
        template = """## Goal
[What the user is trying to accomplish]

## Progress
### Done
[Completed work]
### In Progress
[Work currently underway]

## Key Decisions
[Important decisions made]

## Resolved Questions
[Questions already answered]

## Pending Asks
[Questions not yet answered]

## Remaining Work
[What remains to be done]

Target ~{budget} tokens. Be specific."""

        prompt = f"""{preamble}

TURNS TO SUMMARIZE:
{content}

{template.format(budget=max_tokens)}"""
        
        payload = {
            "model": self.summary_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens * 2,
            "temperature": 0.3
        }
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status != 200:
                        logger.debug(f"Summary LLM HTTP {resp.status}")
                        return None
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.debug(f"LLM call error: {e}")
            return None
    
    def _with_prefix(self, summary: str) -> str:
        text = (summary or "").strip()
        for prefix in (LEGACY_PREFIX, SUMMARY_PREFIX):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break
        return f"{SUMMARY_PREFIX}\n{text}" if text else SUMMARY_PREFIX
    
    def _sanitize_tool_pairs(self, messages: List[Dict]) -> List[Dict]:
        surviving_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    cid = tc.get("id") or ""
                    if cid:
                        surviving_ids.add(cid)
        
        result_ids = set()
        for msg in messages:
            if msg.get("role") == "tool":
                cid = msg.get("tool_call_id")
                if cid:
                    result_ids.add(cid)
        
        orphaned = result_ids - surviving_ids
        if orphaned:
            messages = [m for m in messages if not (m.get("role") == "tool" and m.get("tool_call_id") in orphaned)]
            if not self.quiet_mode:
                logger.info(f"Removed {len(orphaned)} orphaned tool results")
        
        missing = surviving_ids - result_ids
        if missing:
            patched = []
            for msg in messages:
                patched.append(msg)
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls") or []:
                        cid = tc.get("id") or ""
                        if cid in missing:
                            patched.append({
                                "role": "tool",
                                "content": "[Result from earlier conversation]",
                                "tool_call_id": cid,
                            })
            messages = patched
        
        return messages
    
    def _find_tail_cut_by_tokens(self, messages: List[Dict], head_end: int) -> int:
        n = len(messages)
        min_tail = min(3, n - head_end - 1) if n - head_end > 1 else 0
        soft_ceiling = int(self.tail_token_budget * 1.5)
        accumulated = 0
        cut_idx = n
        
        for i in range(n - 1, head_end - 1, -1):
            msg = messages[i]
            content = msg.get("content") or ""
            msg_tokens = len(content) // _CHARS_PER_TOKEN + 10
            
            for tc in msg.get("tool_calls") or []:
                args = tc.get("function", {}).get("arguments", "") or ""
                msg_tokens += len(args) // _CHARS_PER_TOKEN
            
            if accumulated + msg_tokens > soft_ceiling and (n - i) >= min_tail:
                break
            accumulated += msg_tokens
            cut_idx = i
        
        fallback_cut = n - min_tail
        if cut_idx > fallback_cut:
            cut_idx = fallback_cut
        if cut_idx <= head_end:
            cut_idx = max(fallback_cut, head_end + 1)
        
        return max(cut_idx, head_end + 1)
    
    def _align_boundary_forward(self, messages: List[Dict], idx: int) -> int:
        while idx < len(messages) and messages[idx].get("role") == "tool":
            idx += 1
        return idx
    
    def _align_boundary_backward(self, messages: List[Dict], idx: int) -> int:
        """Align backward to non-tool message boundary."""
        while idx > 0 and messages[idx - 1].get("role") == "tool":
            idx -= 1
        return max(idx, 0)
    
    @staticmethod
    def _get_tool_call_id(msg: Dict) -> Optional[str]:
        """Extract tool call ID from a message dict."""
        if msg.get("role") != "tool":
            return None
        # 优先从tool_call_id获取
        tc_id = msg.get("tool_call_id")
        if tc_id:
            return tc_id
        # 兼容其他格式
        tool_calls = msg.get("tool_calls", [])
        if tool_calls and isinstance(tool_calls[0], dict):
            return tool_calls[0].get("id")
        return None
    
    async def compress(
        self, 
        messages: List[Dict], 
        current_tokens: int = None,
        focus_topic: str = None
    ) -> Tuple[List[Dict], CompressionResult]:
        n_messages = len(messages)
        _min_for_compress = self.protect_first_n + 3 + 1
        
        display_tokens = current_tokens or self._estimate_tokens(messages)
        
        # 统一判断：token超过阈值 且 消息数足够
        if display_tokens < self.threshold_tokens or n_messages <= _min_for_compress:
            return messages, CompressionResult(
                original_count=n_messages,
                compressed_count=n_messages,
                original_tokens=display_tokens,
                compressed_tokens=display_tokens,
            )
        
        # Phase 1: 修剪
        messages, pruned_count = self._prune_old_tool_results(
            messages, 
            protect_tail_count=self.protect_first_n,
            protect_tail_tokens=self.tail_token_budget
        )
        
        # Phase 2: 边界
        compress_start = self._align_boundary_forward(messages, self.protect_first_n)
        compress_end = self._find_tail_cut_by_tokens(messages, compress_start)
        
        if compress_start >= compress_end:
            return messages, CompressionResult(
                original_count=n_messages,
                compressed_count=n_messages,
                original_tokens=display_tokens,
                compressed_tokens=display_tokens,
            )
        
        turns_to_summarize = messages[compress_start:compress_end]
        
        # Phase 3: 摘要
        summary, summary_mode = await self._generate_summary(turns_to_summarize)
        
        # Phase 4: 组装
        compressed = []
        
        for i in range(compress_start):
            msg = messages[i].copy()
            if i == 0 and msg.get("role") == "system" and self.compression_count == 0:
                note = "\n\n[Note: Some earlier turns have been compacted.]"
                msg["content"] = (msg.get("content") or "") + note
            compressed.append(msg)
        
        if summary:
            last_head_role = messages[compress_start - 1].get("role") if compress_start > 0 else "user"
            first_tail_role = messages[compress_end].get("role") if compress_end < n_messages else "user"
            
            if last_head_role in ("assistant", "tool"):
                summary_role = "user"
            else:
                summary_role = "assistant"
            
            if summary_role == first_tail_role:
                summary_role = "assistant" if summary_role == "user" else "user"
            
            compressed.append({"role": summary_role, "content": summary})
        else:
            compressed.append({
                "role": "user",
                "content": f"{SUMMARY_PREFIX}\n{compress_end - compress_start} turns removed.\nContinue."
            })
        
        for i in range(compress_end, n_messages):
            compressed.append(messages[i].copy())
        
        self.compression_count += 1
        compressed = self._sanitize_tool_pairs(compressed)
        
        compressed_tokens = self._estimate_tokens(compressed)
        
        result = CompressionResult(
            original_count=n_messages,
            compressed_count=len(compressed),
            original_tokens=display_tokens,
            compressed_tokens=compressed_tokens,
            summary=summary or "",
            pruned_tool_count=pruned_count,
            compression_count=self.compression_count,
            summary_mode=summary_mode
        )
        
        if not self.quiet_mode:
            logger.info(
                f"Compression #{self.compression_count}: "
                f"{n_messages}->{len(compressed)}, "
                f"{display_tokens}->{compressed_tokens} tokens, "
                f"mode={summary_mode}"
            )
        
        return compressed, result
    
    def reset(self):
        self._previous_summary = None
        self.compression_count = 0
        self._summary_failure_cooldown_until = 0.0

    def reset_history(self) -> None:
        """Alias for ``MimirAetherAgent.reset`` / gateway compatibility."""
        self.reset_step()

    def reset_step(self) -> None:
        """Reset per-step state (turn-level, not session-level)."""
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0
        self.reset()


# ============================================================================
# Standalone helper functions
# ============================================================================

def _with_summary_prefix(summary: str) -> str:
    """
    将摘要文本标准化为当前compaction handoff格式（Hermès兼容）

    移除旧前缀（LEGACY_PREFIX或SUMMARY_PREFIX），
    然后添加当前SUMMARY_PREFIX。
    """
    text = (summary or "").strip()
    for prefix in (LEGACY_PREFIX, SUMMARY_PREFIX):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
            break
    return f"{SUMMARY_PREFIX}\n{text}" if text else SUMMARY_PREFIX


# 向后兼容导出（core_loop.py使用ContextCompressor）
ContextCompressor = ContextCompressorV2


def compress_conversation(messages: List[Dict], **kwargs) -> Tuple[List[Dict], CompressionResult]:
    # 分离ContextCompressorV2的__init__参数和其他参数
    init_keys = {'model', 'threshold_percent', 'protect_first_n', 'protect_last_n', 
                 'tail_token_budget', 'summary_target_ratio', 'summary_model', 
                 'base_url', 'api_key', 'credential_pool', 'model_context_length'}
    init_kwargs = {k: v for k, v in kwargs.items() if k in init_keys}
    
    compressor = ContextCompressorV2(**init_kwargs)
    tokens = compressor._estimate_tokens(messages)
    if not compressor.should_compress(prompt_tokens=tokens):
        return messages, CompressionResult(
            original_count=len(messages),
            compressed_count=len(messages),
            original_tokens=tokens,
            compressed_tokens=tokens,
        )
    return compressor.compress(messages)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("ContextCompressor V2.2 测试")
    print("=" * 60)
    
    # 测试1: 基本压缩
    print("\n[测试1] 基本压缩测试")
    test_messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a Python function to sort a list"},
        {"role": "assistant", "content": "Here is a quick sort implementation..."},
        {"role": "tool", "tool_call_id": "tc1", "content": "User wants to sort [3,1,4,1,5]"},
        {"role": "user", "content": "Can you make it more efficient?"},
        {"role": "assistant", "content": "Sure! Using merge sort with O(n log n)..."},
    ] * 15
    
    compressor = ContextCompressorV2(quiet_mode=False)
    tokens = compressor._estimate_tokens(test_messages)
    print(f"输入: {len(test_messages)} 条消息, ~{tokens} tokens")
    print(f"应压缩: {compressor.should_compress(test_messages, tokens)}")
    
    compressed, result = compressor.compress(test_messages)
    
    print(f"\n结果:")
    print(f"  压缩后: {result.compressed_count} 条消息")
    print(f"  Token节省: {result.original_tokens - result.compressed_tokens}")
    print(f"  摘要模式: {result.summary_mode}")
    print(f"  摘要长度: {len(result.summary)} 字符")
    
    # 测试2: 短对话不压缩
    print("\n[测试2] 短对话不压缩")
    short_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    tokens2 = compressor._estimate_tokens(short_messages)
    compressed2, result2 = compressor.compress(short_messages)
    print(f"  输入: {len(short_messages)} msg, ~{tokens2} tokens")
    print(f"  应压缩: {compressor.should_compress(short_messages, tokens2)}")
    print(f"  输出: {len(compressed2)} msg")
    
    # 测试3: 迭代压缩
    print("\n[测试3] 迭代压缩")
    compressor.reset()
    comp1, res1 = compressor.compress(test_messages)
    tokens_c1 = compressor._estimate_tokens(comp1)
    print(f"  第1次: {res1.compressed_count} msg, ~{tokens_c1} tokens, 应压缩={compressor.should_compress(comp1, tokens_c1)}")
    
    comp2, res2 = compressor.compress(comp1)
    tokens_c2 = compressor._estimate_tokens(comp2)
    print(f"  第2次: {res2.compressed_count} msg, ~{tokens_c2} tokens, 应压缩={compressor.should_compress(comp2, tokens_c2)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

# ============================================================================
# Full-Featured Compressor with Probing Support
# ============================================================================

class MimirContextCompressor(ContextCompressorV2):
    """
    Full-featured context compressor with probing support.
    
    Compression strategy:
    1. 工具结果修剪（无LLM调用）
    2. 保护头部消息（system + first exchange）
    3. 保护尾部消息（按token预算）
    4. LLM摘要中间消息
    5. 迭代摘要更新
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # calls ContextCompressorV2.__init__
        # Extra configuration
        self._iterative_summary = True  # 迭代摘要
        self._tool_pruning_enabled = True
        self._context_probed = False
    
    def reset_step(self) -> None:
        """Reset per-step state."""
        super().reset_step()
        self._context_probed = False
        self._previous_summary = None
    
    def mark_context_probed(self) -> None:
        """标记上下文已探测（从上下文错误恢复后）"""
        self._context_probed = True
    
    def is_context_probed(self) -> bool:
        """检查是否已探测上下文"""
        return self._context_probed
    
    def prune_tool_results_aggressive(
        self, 
        messages: List[Dict],
        keep_last: int = 5
    ) -> List[Dict]:
        """
        激进工具结果修剪
        
        : 清除旧工具输出以节省上下文空间
        """
        if not messages:
            return messages
        
        result = []
        tool_count = 0
        
        for msg in messages:
            msg_copy = msg.copy()
            content = msg.get("content", "")
            
            # 检测工具消息
            if msg.get("role") == "tool" or "tool_call" in str(msg):
                tool_count += 1
                # 保留最近N个工具结果
                if tool_count > keep_last:
                    msg_copy["content"] = _PRUNED_TOOL_PLACEHOLDER
            
            result.append(msg_copy)
        
        return result
    
    def protect_tail_by_tokens(
        self,
        messages: List[Dict],
        token_budget: int
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        按token预算保护尾部消息
        
        : 使用token预算而不是固定消息数
        """
        if not messages or token_budget <= 0:
            return [], messages
        
        protected = []
        current_tokens = 0
        
        # 从后向前保护
        for msg in reversed(messages):
            content = msg.get("content", "") or ""
            msg_tokens = len(content) // _CHARS_PER_TOKEN + 50  # 估算开销
            
            if current_tokens + msg_tokens <= token_budget:
                protected.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # 分割点
                break
        
        # 未保护的部分
        unprotected = messages[:-len(protected)] if protected else messages
        
        return unprotected, protected
    
    def get_compression_ratio(self) -> float:
        """获取压缩比率"""
        if self.original_tokens == 0:
            return 0.0
        return 1.0 - (self.compressed_tokens / self.original_tokens)
    
    def should_trigger_compression(
        self,
        prompt_tokens: int,
        completion_tokens: int = 0,
        include_reserve: bool = True
    ) -> Tuple[bool, str]:
        """
        判断是否应触发压缩
        
        Returns:
            (should_compress, reason)
        """
        total_tokens = prompt_tokens + completion_tokens
        
        # 检查阈值
        if total_tokens >= self.threshold_tokens:
            reserve = 2000 if include_reserve else 0
            if total_tokens >= self.threshold_tokens + reserve:
                return True, f"Exceeded threshold: {total_tokens} >= {self.threshold_tokens + reserve}"
        
        # 检查冷却
        if time.time() < self._summary_failure_cooldown_until:
            return False, "In cooldown period"
        
        # 检查是否已探测
        if self._context_probed:
            # 已经压缩过，警告但允许
            return True, "Context already probed, re-compression allowed"
        
        return False, "Within safe bounds"


# Backward compatibility alias
HermesStyleCompressor = MimirContextCompressor
