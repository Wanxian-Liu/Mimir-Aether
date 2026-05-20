"""
RecoveryMixin — Error recovery: DecisionRing-driven + history truncation + orphan cleanup.

Extracted from MimirAetherAgent (agent/core_loop.py) as part of d4 split.
"""

from __future__ import annotations


from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .types import Message, MessageRole

if TYPE_CHECKING:
    from agent.core_loop import MimirAetherAgent

import logging
logger = logging.getLogger(__name__)

class RecoveryMixin:
    """Error recovery: DecisionRing-driven + history truncation + orphan cleanup.

    Designed to be mixed into MimirAetherAgent.
    """
    def get_recovery_stats(self) -> str:
        """获取恢复统计"""
        return self.recovery.format_stats()
    
    async def handle_error_with_recovery(
        self,
        error: Exception,
        context: dict = None
    ) -> bool:
        """
        使用多层次恢复处理错误（P0-2: DecisionRing 驱动恢复策略）
        
        不再使用 ad-hoc 字符串匹配；改为 DecisionRing 结构化分类 →
        14 FailoverReason × 16 StrategyAction 的完整决策矩阵。
        
        层次:
          1. RETRY - 由外层 _model_call_adapter 重试（本方法不处理）
          2. COMPRESS - context_overflow / payload_too_large → 压缩+截断
          3. TRUNCATE - 通用恢复 → 截断+清理孤儿
          4. DEGRADE - rate_limit / billing / overloaded / server_error → 备用模型
        
        Args:
            error: 发生的错误
            context: 错误上下文
            
        Returns:
            是否恢复成功（True = 已采取措施，外部可重试）
        """
        from .error_classifier import FailoverReason
        from .strategy_matcher import StrategyAction
        
        _err_str = str(error)
        
        # P0-2c: DecisionRing 结构化分类替代 ad-hoc 字符串匹配
        _provider = self.model.split("/")[0] if "/" in self.model else ""
        _decision = self.decision_ring.decide(
            error, provider=_provider, model=self.model,
        )
        _reason = _decision.classified_error.reason
        _actions = set(_decision.suggested_actions)
        
        recovered = False
        
        # Level 2: COMPRESS — context_overflow / payload_too_large
        _needs_compress = (
            _reason in (FailoverReason.context_overflow, FailoverReason.payload_too_large)
            or StrategyAction.COMPRESS_CONTEXT in _actions
        )
        if _needs_compress and self.compressor:
            logger.info("[Recovery] Level 2 COMPRESS (DecisionRing: %s): %s",
                       _reason.value if _reason else "unknown", _err_str[:100])
            self.budget.stats.compression_triggered += 1
            self.compressor.mark_context_probed()
            await self._truncate_history()
            self._clean_orphan_tools()
            recovered = True
        
        # Level 3: TRUNCATE — 通用截断（降级）
        _needs_truncate = (
            not recovered
            or StrategyAction.TRUNCATE_CONTEXT in _actions
            or StrategyAction.REDUCE_PAYLOAD in _actions
        )
        if _needs_truncate:
            logger.info("[Recovery] Level 3 TRUNCATE (DecisionRing: %s): %s",
                       _reason.value if _reason else "unknown", _err_str[:100])
            await self._truncate_history()
            self._clean_orphan_tools()
            recovered = True
        
        # Level 4: DEGRADE — rate_limit / billing / overloaded / server_error
        _needs_fallback = (
            _reason in (
                FailoverReason.rate_limit, FailoverReason.billing,
                FailoverReason.overloaded, FailoverReason.server_error,
                FailoverReason.auth, FailoverReason.timeout,
                FailoverReason.model_not_found,
            )
            or StrategyAction.FALLBACK_PROVIDER in _actions
            or StrategyAction.DOWNGRADE_MODEL in _actions
            or not recovered  # 兜底：前三层都没恢复就切模型
        )
        if _needs_fallback:
            if self._try_activate_fallback():
                logger.info("[Recovery] Level 4 DEGRADE (DecisionRing: %s): switched to fallback",
                           _reason.value if _reason else "unknown")
            else:
                logger.warning("[Recovery] No fallback available (DecisionRing: %s)",
                              _reason.value if _reason else "unknown")
        
        return recovered
    
    # ── DEPRECATED since d4 — superseded by handle_error_with_recovery + DecisionRing ──
    # Kept for reference; zero callers as of d4. Remove after 2026Q3 if unused.
    async def _recovery_error_handler(
        self, 
        error: Exception, 
        context: RecoveryContext
    ) -> None:
        """[DEPRECATED] 恢复错误处理器 — 已由 handle_error_with_recovery 替代"""
        logger.warning("[DEPRECATED] _recovery_error_handler called — redirecting to handle_error_with_recovery")
        await self.handle_error_with_recovery(error)
        return
        
        # Dead code below preserved for historical reference
        level = context.current_level
        logger.warning(f"Recovery at level {level.value}: {error}")
        
        if level == RecoveryLevel.COMPRESS:
            # 触发上下文压缩
            self.budget.stats.compression_triggered += 1
            self.compressor.mark_context_probed()
            await self._emit_status("🔄 Compressing context...")
            
        elif level == RecoveryLevel.TRUNCATE:
            # 强制截断历史
            await self._truncate_history()
            await self._emit_status("✂️ Truncating history...")
    
    async def _truncate_history(self, keep_recent: int = 10) -> None:
        """截断对话历史（保完整 tool pair，不切中间）"""
        if len(self.conversation_history) <= keep_recent:
            return
        boundary = self._find_safe_truncation_boundary(keep_recent)
        truncated = self.conversation_history[boundary:]
        removed = len(self.conversation_history) - len(truncated)
        self.conversation_history = truncated
        logger.info(
            f"Truncated {removed} messages (safe boundary at idx {boundary}, "
            f"kept {len(truncated)} messages)"
        )

    def _find_safe_truncation_boundary(self, max_keep: int) -> int:
        """找到安全的截断边界，不切断 tool pair。
        
        从尾部 max_keep 条的位置向前扫描，找到第一个安全的切点：
        - tool 消息需要 paired assistant（含 tool_calls）也在保留范围内
        - assistant（含 tool_calls）需要所有配对的 tool 结果也在保留范围内
        
        返回：应保留的消息起始索引（从该位置开始的消息全部保留）。
        """
        n = len(self.conversation_history)
        if n <= max_keep:
            return 0
        
        # 从 max_keep 位置开始，向前找到安全边界
        # 收集保留范围内所有 assistant 的 tool_call IDs
        tail_start = n - max_keep
        pending_tool_ids: set = set()
        
        for idx in range(tail_start, n):
            msg = self.conversation_history[idx]
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if isinstance(tc, dict) and "id" in tc:
                        pending_tool_ids.add(tc["id"])
            if msg.tool_call_id:
                pending_tool_ids.discard(msg.tool_call_id)
        
        # 向前扩展直到所有 tool pair 都闭合
        boundary = tail_start
        for idx in range(tail_start - 1, -1, -1):
            if not pending_tool_ids:
                break
            msg = self.conversation_history[idx]
            if msg.tool_call_id:
                pending_tool_ids.add(msg.tool_call_id)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if isinstance(tc, dict) and "id" in tc:
                        pending_tool_ids.discard(tc["id"])
            boundary = idx
        
        return boundary

    def _clean_orphan_tools(self) -> int:
        """统一委托给 compressor._sanitize_tool_pairs — 唯一 canonical 实现。
        
        （P0-1 统一入口：core_loop._sanitize_tool_messages + core_loop._clean_orphan_tools
         + compressor._sanitize_tool_pairs 三合一）
        
        旧逻辑删除缺 tool 结果的 assistant 消息（丢失文本内容）；
        新逻辑保留 assistant 消息，为缺失的 tool 结果补占位符。
        """
        if not self.conversation_history:
            return 0
        pre = len(self.conversation_history)
        # 转为 dict 列表 → 调用 canonical 清理 → 转回 Message 对象
        msg_dicts = [
            {
                "role": m.role.value,
                "content": m.content,
                "name": m.name,
                "tool_calls": m.tool_calls,
                "tool_call_id": m.tool_call_id,
            }
            for m in self.conversation_history
        ]
        cleaned_dicts = self.compressor._sanitize_tool_pairs(msg_dicts)
        self.conversation_history = [
            Message(
                role=MessageRole(d["role"]),
                content=d.get("content", ""),
                name=d.get("name"),
                tool_calls=d.get("tool_calls"),
                tool_call_id=d.get("tool_call_id"),
            )
            for d in cleaned_dicts
        ]
        cleaned = pre - len(self.conversation_history)
        if cleaned:
            logger.warning("Cleaned %d orphaned message(s) from conversation_history", cleaned)
        return cleaned

    def _sanitize_tool_messages(self, messages: List[Dict]) -> List[Dict]:
        """统一委托给 compressor._sanitize_tool_pairs — 唯一 canonical 实现。

        （P0-1 统一入口：core_loop._sanitize_tool_messages + core_loop._clean_orphan_tools
         + compressor._sanitize_tool_pairs 三合一）
        """
        return self.compressor._sanitize_tool_pairs(messages)

