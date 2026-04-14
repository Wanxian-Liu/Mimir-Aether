"""
MimirAether 子Agent系统

支持任务分解和并行执行的子Agent管理。
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SubAgentStatus(Enum):
    """子Agent状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubAgentTask:
    """子Agent任务"""
    id: str
    name: str
    description: str
    status: SubAgentStatus = SubAgentStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class TaskDecomposition:
    """任务分解结果"""
    main_task: str
    subtasks: List[Dict[str, Any]]
    estimated_complexity: int = 0
    estimated_time: int = 0  # 秒


class SubAgentPool:
    """
    子Agent池
    
    管理多个子Agent的并行执行。
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._tasks: Dict[str, SubAgentTask] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._task_lock = asyncio.Lock()
        self._running_tasks: List[asyncio.Task] = []
        
        logger.info(f"SubAgentPool initialized with max_concurrent={max_concurrent}")
    
    async def execute_subtask(
        self,
        task_id: str,
        handler: Callable,
        args: tuple = (),
        kwargs: Dict = None
    ) -> Any:
        """
        执行子任务
        
        Args:
            task_id: 任务ID
            handler: 处理函数
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            任务结果
        """
        if kwargs is None:
            kwargs = {}
        
        async with self._semaphore:
            if task_id in self._tasks:
                self._tasks[task_id].status = SubAgentStatus.RUNNING
                self._tasks[task_id].started_at = datetime.now().isoformat()
            
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(*args, **kwargs)
                else:
                    result = handler(*args, **kwargs)
                
                if task_id in self._tasks:
                    self._tasks[task_id].status = SubAgentStatus.COMPLETED
                    self._tasks[task_id].result = result
                    self._tasks[task_id].completed_at = datetime.now().isoformat()
                
                return result
                
            except Exception as e:
                logger.error(f"SubTask {task_id} failed: {e}")
                if task_id in self._tasks:
                    self._tasks[task_id].status = SubAgentStatus.FAILED
                    self._tasks[task_id].error = str(e)
                raise
    
    def create_task(
        self,
        name: str,
        description: str,
        handler: Callable,
        args: tuple = (),
        kwargs: Dict = None
    ) -> str:
        """
        创建子任务
        
        Args:
            name: 任务名称
            description: 任务描述
            handler: 处理函数
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            任务ID
        """
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        self._tasks[task_id] = SubAgentTask(
            id=task_id,
            name=name,
            description=description
        )
        
        logger.info(f"Created subtask: {task_id} - {name}")
        return task_id
    
    async def execute_parallel(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        并行执行多个任务
        
        Args:
            tasks: 任务列表，每个任务包含:
                - name: 任务名称
                - handler: 处理函数
                - args: 位置参数
                - kwargs: 关键字参数
                
        Returns:
            结果列表
        """
        task_ids = []
        coroutines = []
        
        for task in tasks:
            task_id = self.create_task(
                name=task.get("name", "unnamed"),
                description=task.get("description", ""),
                handler=task.get("handler"),
                args=task.get("args", ()),
                kwargs=task.get("kwargs", {})
            )
            task_ids.append(task_id)
            
            coroutines.append(
                self.execute_subtask(
                    task_id=task_id,
                    handler=task.get("handler"),
                    args=task.get("args", ()),
                    kwargs=task.get("kwargs", {})
                )
            )
        
        # 并行执行所有任务
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {task_ids[i]} failed: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_task(self, task_id: str) -> Optional[SubAgentTask]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[SubAgentTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._task_lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = SubAgentStatus.CANCELLED
                return True
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        tasks = list(self._tasks.values())
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == SubAgentStatus.PENDING),
            "running": sum(1 for t in tasks if t.status == SubAgentStatus.RUNNING),
            "completed": sum(1 for t in tasks if t.status == SubAgentStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == SubAgentStatus.FAILED),
        }


class TaskDecomposer:
    """
    任务分解器
    
    将复杂任务分解为可并行执行的子任务。
    """
    
    def __init__(self, max_subtasks: int = 10):
        self.max_subtasks = max_subtasks
    
    async def decompose(
        self,
        task: str,
        context: Dict[str, Any] = None
    ) -> TaskDecomposition:
        """
        分解任务
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            任务分解结果
        """
        # 简单的启发式分解
        # 实际应该调用LLM进行智能分解
        
        subtasks = []
        
        # 检测是否需要分解
        keywords = ["并且", "同时", "还有", "另外", "分别", "并行"]
        has_parallel = any(kw in task for kw in keywords)
        
        if has_parallel:
            # 简单分割
            parts = task.replace("并且", "|").replace("同时", "|").replace("还有", "|").replace("另外", "|").replace("分别", "|").replace("，", "|").split("|")
            for i, part in enumerate(parts[:self.max_subtasks]):
                part = part.strip()
                if part:
                    subtasks.append({
                        "id": f"subtask_{i}",
                        "name": f"子任务 {i+1}",
                        "description": part,
                        "priority": 1
                    })
        else:
            # 单任务
            subtasks.append({
                "id": "subtask_1",
                "name": "主任务",
                "description": task,
                "priority": 1
            })
        
        return TaskDecomposition(
            main_task=task,
            subtasks=subtasks,
            estimated_complexity=len(subtasks),
            estimated_time=len(subtasks) * 30  # 假设每个任务30秒
        )


# 导出的类和函数
__all__ = [
    "SubAgentPool",
    "SubAgentTask",
    "SubAgentStatus",
    "TaskDecomposer",
    "TaskDecomposition",
]
