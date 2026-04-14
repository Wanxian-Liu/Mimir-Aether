"""
MimirAether Turn Loop

管理对话的轮次（Turn），每个Turn代表一次用户-助手交互。

核心功能：
- Turn生命周期管理
- 多轮对话状态跟踪
- Turn级别的预算控制（可选）
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from .core_loop import MimirAetherAgent, Message, MessageRole

logger = logging.getLogger(__name__)


class TurnStatus(Enum):
    """Turn状态"""
    IDLE = "idle"                    # 空闲
    RUNNING = "running"              # 运行中
    COMPLETED = "completed"          # 完成
    FAILED = "failed"               # 失败
    MAX_ITERATIONS = "max_iterations"  # 达到最大迭代


@dataclass
class Turn:
    """
    单轮对话
    
    代表一次完整的用户-助手交互
    """
    id: str
    user_message: str
    assistant_message: Optional[str] = None
    status: TurnStatus = TurnStatus.IDLE
    iterations: int = 0
    tool_calls: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "status": self.status.value,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "error": self.error
        }


class TurnManager:
    """
    Turn管理器
    
    管理多轮对话的Turn，支持：
    - 创建和管理Turn
    - Turn状态跟踪
    - 统计信息收集
    """
    
    def __init__(self, agent: MimirAetherAgent):
        self.agent = agent
        self.turns: List[Turn] = []
        self.current_turn: Optional[Turn] = None
        self._turn_counter = 0
        
        logger.info("TurnManager initialized")
    
    def create_turn(self, user_message: str) -> Turn:
        """创建新Turn"""
        self._turn_counter += 1
        turn = Turn(
            id=f"turn_{self._turn_counter}",
            user_message=user_message
        )
        self.turns.append(turn)
        self.current_turn = turn
        return turn
    
    async def execute_turn(self, user_message: str) -> str:
        """
        执行一个Turn
        
        Args:
            user_message: 用户消息
            
        Returns:
            助手响应文本
        """
        # 先检查预算，再创建turn
        if hasattr(self.agent, 'budget'):
            remaining = self.agent.budget.remaining
            if remaining <= 0:
                # 创建turn记录，但标记为max_iterations
                turn = self.create_turn(user_message)
                turn.status = TurnStatus.MAX_ITERATIONS
                turn.error = "迭代次数已达上限"
                return "抱歉，任务迭代次数已达上限，请重试。"
        
        turn = self.create_turn(user_message)
        turn.status = TurnStatus.RUNNING
        
        try:
            # 调用Agent处理
            response = await self.agent.chat(user_message)
            
            turn.assistant_message = response
            turn.status = TurnStatus.COMPLETED
            
            # 记录迭代次数
            if hasattr(self.agent, 'budget'):
                turn.iterations = self.agent.budget._used
            
            logger.info(f"Turn {turn.id} completed: {len(response)} chars, iterations: {turn.iterations}")
            return response
            
        except Exception as e:
            logger.error(f"Turn {turn.id} failed: {e}")
            turn.status = TurnStatus.FAILED
            turn.error = str(e)
            raise
    
    def get_turn_history(self) -> List[Dict[str, Any]]:
        """获取Turn历史"""
        return [turn.to_dict() for turn in self.turns]
    
    def get_last_turn(self) -> Optional[Turn]:
        """获取最后一个Turn"""
        if self.turns:
            return self.turns[-1]
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.turns)
        completed = sum(1 for t in self.turns if t.status == TurnStatus.COMPLETED)
        failed = sum(1 for t in self.turns if t.status == TurnStatus.FAILED)
        max_iterations = sum(1 for t in self.turns if t.status == TurnStatus.MAX_ITERATIONS)
        running = sum(1 for t in self.turns if t.status == TurnStatus.RUNNING)
        
        return {
            "total_turns": total,
            "completed": completed,
            "failed": failed,
            "max_iterations": max_iterations,
            "running": running,
            "success_rate": completed / total if total > 0 else 0,
            "total_iterations": sum(t.iterations for t in self.turns if t.iterations > 0)
        }
    
    async def reset(self):
        """重置Turn管理器"""
        self.turns = []
        self.current_turn = None
        self._turn_counter = 0
        await self.agent.reset()
        logger.info("TurnManager reset")


# 导出的类和函数
__all__ = [
    "TurnManager",
    "Turn",
    "TurnStatus",
]
