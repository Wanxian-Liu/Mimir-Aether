"""
Checkpoint Manager - 断点续传管理器

定期将任务进度保存到磁盘，支持从断点恢复。
用于解决Gateway连接断开导致长时间任务失败的问题。

使用方法：
1. 任务开始时：load_checkpoint(task_id) 检查是否有未完成的检查点
2. 任务执行中：save_checkpoint(task_id, state) 定期保存进度
3. 任务完成时：clear_checkpoint(task_id) 清除检查点
"""

import json
import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# 检查点存储目录
CHECKPOINT_DIR = Path.home() / ".openclaw" / "projects" / "MimirAether" / "checkpoints"


@dataclass
class CheckpointState:
    """检查点状态"""
    task_id: str
    created_at: float
    updated_at: float
    conversation_history: list  # 序列化的消息历史
    current_step: int  # 当前迭代步骤
    next_action: str  # 下一步计划描述
    iteration_used: int  # 已使用的迭代次数
    user_message: str  # 用户原始消息
    session_id: str  # 会话ID
    metadata: Dict[str, Any]  # 附加元数据


class CheckpointManager:
    """
    检查点管理器
    
    功能：
    - 保存任务状态到JSON文件
    - 从检查点恢复任务
    - 清除已完成的检查点
    - 自动清理过期检查点（24小时）
    """
    
    def __init__(self, checkpoint_dir: Path = None):
        self.checkpoint_dir = checkpoint_dir or CHECKPOINT_DIR
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._max_age_hours = 24  # 24小时过期
    
    def _get_checkpoint_path(self, task_id: str) -> Path:
        """获取检查点文件路径"""
        # 安全：只允许字母数字和短横线
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_id)
        return self.checkpoint_dir / f"checkpoint_{safe_id}.json"
    
    def _generate_task_id(self, user_message: str) -> str:
        """生成稳定的任务ID（基于消息内容的hash）"""
        # 使用消息内容的hash作为task_id，确保相同消息产生相同ID
        hash_obj = hashlib.sha256(user_message.encode('utf-8'))
        return hash_obj.hexdigest()[:16]
    
    def save_checkpoint(
        self,
        task_id: str,
        state: Dict[str, Any],
        current_step: int = 0,
        next_action: str = "继续执行",
    ) -> bool:
        """
        保存检查点
        
        Args:
            task_id: 任务唯一标识符
            state: 完整状态字典，包含：
                - conversation_history: 序列化后的对话历史
                - iteration_used: 已使用的迭代次数
                - session_id: 会话ID
                - user_message: 用户原始消息
            current_step: 当前执行步骤
            next_action: 下一步计划描述
            
        Returns:
            bool: 保存是否成功
        """
        try:
            checkpoint_path = self._get_checkpoint_path(task_id)
            
            checkpoint_data = {
                "task_id": task_id,
                "created_at": state.get("created_at", time.time()),
                "updated_at": time.time(),
                "conversation_history": state.get("conversation_history", []),
                "current_step": current_step,
                "next_action": next_action,
                "iteration_used": state.get("iteration_used", 0),
                "user_message": state.get("user_message", ""),
                "session_id": state.get("session_id", ""),
                "metadata": state.get("metadata", {}),
            }
            
            # 写入临时文件，再原子重命名（防止写入中断导致文件损坏）
            temp_path = checkpoint_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            temp_path.rename(checkpoint_path)
            logger.debug(f"Checkpoint saved: {task_id} at step {current_step}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint {task_id}: {e}")
            return False
    
    def load_checkpoint(self, task_id: str) -> Optional[CheckpointState]:
        """
        加载检查点
        
        Args:
            task_id: 任务唯一标识符
            
        Returns:
            CheckpointState对象，如果不存在或已过期返回None
        """
        try:
            checkpoint_path = self._get_checkpoint_path(task_id)
            
            if not checkpoint_path.exists():
                return None
            
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否过期
            age_hours = (time.time() - data.get("updated_at", 0)) / 3600
            if age_hours > self._max_age_hours:
                logger.info(f"Checkpoint {task_id} expired ({age_hours:.1f}h old), removing")
                self.clear_checkpoint(task_id)
                return None
            
            return CheckpointState(
                task_id=data["task_id"],
                created_at=data.get("created_at", 0),
                updated_at=data.get("updated_at", 0),
                conversation_history=data.get("conversation_history", []),
                current_step=data.get("current_step", 0),
                next_action=data.get("next_action", ""),
                iteration_used=data.get("iteration_used", 0),
                user_message=data.get("user_message", ""),
                session_id=data.get("session_id", ""),
                metadata=data.get("metadata", {}),
            )
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint {task_id}: {e}")
            return None
    
    def clear_checkpoint(self, task_id: str) -> bool:
        """
        清除检查点
        
        Args:
            task_id: 任务唯一标识符
            
        Returns:
            bool: 清除是否成功
        """
        try:
            checkpoint_path = self._get_checkpoint_path(task_id)
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                logger.debug(f"Checkpoint cleared: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear checkpoint {task_id}: {e}")
            return False
    
    def has_checkpoint(self, task_id: str) -> bool:
        """检查是否存在有效检查点"""
        return self.load_checkpoint(task_id) is not None
    
    def cleanup_expired(self) -> int:
        """
        清理所有过期的检查点
        
        Returns:
            清理的检查点数量
        """
        cleaned = 0
        try:
            for f in self.checkpoint_dir.glob("checkpoint_*.json"):
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    age_hours = (time.time() - data.get("updated_at", 0)) / 3600
                    if age_hours > self._max_age_hours:
                        f.unlink()
                        cleaned += 1
                        logger.debug(f"Cleaned expired checkpoint: {f.name}")
                except Exception:
                    pass  # 忽略损坏的文件
        except Exception as e:
            logger.warning(f"Failed to cleanup expired checkpoints: {e}")
        return cleaned
    
    def list_checkpoints(self) -> list:
        """列出所有检查点"""
        checkpoints = []
        try:
            for f in self.checkpoint_dir.glob("checkpoint_*.json"):
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    checkpoints.append({
                        "task_id": data.get("task_id", ""),
                        "updated_at": data.get("updated_at", 0),
                        "current_step": data.get("current_step", 0),
                        "user_message_preview": (data.get("user_message", "") or "")[:50],
                    })
                except Exception:
                    pass
        except Exception:
            pass
        return checkpoints


# 全局单例
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """获取全局检查点管理器实例"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


# 便捷函数
def save_checkpoint(task_id: str, state: Dict[str, Any], current_step: int = 0, next_action: str = "继续执行") -> bool:
    """保存检查点"""
    return get_checkpoint_manager().save_checkpoint(task_id, state, current_step, next_action)


def load_checkpoint(task_id: str) -> Optional[CheckpointState]:
    """加载检查点"""
    return get_checkpoint_manager().load_checkpoint(task_id)


def clear_checkpoint(task_id: str) -> bool:
    """清除检查点"""
    return get_checkpoint_manager().clear_checkpoint(task_id)
