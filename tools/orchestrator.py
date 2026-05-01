"""
工具编排器
支持工具链串联、并行执行、条件路由
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

__all__ = ["ToolChainOrchestrator", "ToolResult", "ChainStep", "ExecutionMode", "Pipeline"]

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"  # 串联
    PARALLEL = "parallel"      # 并行
    CONDITIONAL = "conditional" # 条件路由


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ChainStep:
    """链式步骤"""
    tool_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable[[ToolResult], bool]] = None  # 条件函数


class ToolChainOrchestrator:
    """
    工具链编排器
    
    支持：
    - 串联执行（chain）：按顺序执行工具链
    - 并行执行（parallel）：多个工具同时执行
    - 条件路由（conditional）：根据上一步结果决定下一步
    """
    
    def __init__(self, tool_registry=None, max_concurrency: int = 5):
        self.tool_registry = tool_registry
        self.max_concurrency = max_concurrency
        self._chains: Dict[str, List[ChainStep]] = {}
    
    def register_chain(self, name: str, steps: List[ChainStep]) -> None:
        """注册工具链"""
        self._chains[name] = steps
        logger.info(f"Registered chain: {name} with {len(steps)} steps")
    
    async def execute_chain(
        self, 
        chain_name: str, 
        initial_input: Any = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """执行工具链"""
        if chain_name not in self._chains:
            raise ValueError(f"Chain '{chain_name}' not found")
        
        steps = self._chains[chain_name]
        context = context or {}
        results = []
        current_input = initial_input
        
        for i, step in enumerate(steps):
            # 条件检查（首个步骤无条件执行）
            if step.condition and results:
                try:
                    if not step.condition(results[-1]):
                        logger.info(f"Step {i} skipped due to condition")
                        continue
                except Exception as e:
                    logger.warning(f"Step {i} condition evaluation failed: {e}, executing anyway")
            
            # 执行工具
            result = await self._execute_tool(
                step.tool_name, 
                step.params,
                context,
                current_input
            )
            results.append(result)
            
            if not result.success:
                logger.warning(f"Tool {step.tool_name} failed, continuing chain")
            
            # 更新输入上下文
            if result.output is not None:
                current_input = result.output
                context[f"step_{i}_output"] = result.output
        
        return results
    
    async def execute_parallel(
        self,
        tool_calls: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        max_concurrency: Optional[int] = None
    ) -> List[ToolResult]:
        """并行执行多个工具"""
        context = context or {}
        
        # 限制并发数
        semaphore = asyncio.Semaphore(max_concurrency or self.max_concurrency)
        
        async def bounded_execute(call):
            async with semaphore:
                return await self._execute_tool(
                    call["tool_name"],
                    call.get("params", {}),
                    context,
                    call.get("input")
                )
        
        tasks = [bounded_execute(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ToolResult(
                    tool_name=tool_calls[i].get("tool_name", "unknown"),
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def execute_conditional(
        self,
        condition_fn: Callable[[Any], str],  # 返回下一个工具名
        tools: Dict[str, Dict[str, Any]],
        initial_input: Any = None,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 20
    ) -> ToolResult:
        """条件路由执行"""
        context = context or {}
        current_input = initial_input
        iterations = 0
        tool_name = condition_fn(current_input)
        
        while tool_name and tool_name in tools:
            iterations += 1
            if iterations > max_iterations:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Max iterations ({max_iterations}) exceeded in conditional execution"
                )
            call = tools[tool_name]
            result = await self._execute_tool(
                call["tool_name"],
                call.get("params", {}),
                context,
                current_input
            )
            
            if not result.success:
                return result
            
            current_input = result.output
            context["last_output"] = result.output
            tool_name = condition_fn(current_input)
        
        return ToolResult(
            tool_name=tool_name or "none",
            success=True,
            output=current_input
        )
    
    async def _execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        input_data: Any
    ) -> ToolResult:
        """执行单个工具"""
        import time
        start = time.time()
        
        try:
            if self.tool_registry is None:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error="Tool registry not configured"
                )
            
            # 获取工具
            tool_func = self.tool_registry.get_tool(tool_name)
            if tool_func is None:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Tool '{tool_name}' not found"
                )
            
            # 合并参数和上下文
            exec_params = {**params}
            if input_data is not None:
                exec_params["input"] = input_data
            exec_params["context"] = context
            
            # 执行
            if asyncio.iscoroutinefunction(tool_func):
                output = await tool_func(**exec_params)
            else:
                output = tool_func(**exec_params)
            
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=output,
                duration=time.time() - start
            )
            
        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error="Tool execution timed out",
                duration=time.time() - start
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Error: {type(e).__name__} - {e}",
                duration=time.time() - start
            )
    
    def list_chains(self) -> List[str]:
        """列出所有注册的链"""
        return list(self._chains.keys())
    
    def get_chain_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取链信息"""
        if name not in self._chains:
            return None
        
        steps = self._chains[name]
        return {
            "name": name,
            "step_count": len(steps),
            "steps": [
                {"tool": s.tool_name, "has_condition": s.condition is not None}
                for s in steps
            ]
        }


# Pipeline 装饰器
class Pipeline:
    """流水线装饰器"""
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[ChainStep] = []
    
    def step(self, tool_name: str, params: Dict[str, Any] = None):
        """添加步骤"""
        def decorator(func: Callable) -> Callable:
            self.steps.append(ChainStep(
                tool_name=tool_name,
                params=params or {},
                condition=func
            ))
            return func
        return decorator
    
    def build(self, orchestrator: ToolChainOrchestrator):
        """构建到编排器"""
        orchestrator.register_chain(self.name, self.steps)


# 使用示例
async def example_usage():
    """使用示例"""
    orchestrator = ToolChainOrchestrator()
    
    # 定义链
    chain = [
        ChainStep("search", {"query": "weather"}),
        ChainStep("parse", {"format": "json"}),
        ChainStep("format", {"template": "today: {temp}°C"}),
    ]
    orchestrator.register_chain("weather", chain)
    
    # 执行
    results = await orchestrator.execute_chain("weather", initial_input="Beijing")
    
    for r in results:
        print(f"{r.tool_name}: {'✓' if r.success else '✗'} - {r.output}")
    
    # 并行执行
    parallel_results = await orchestrator.execute_parallel([
        {"tool_name": "search", "params": {"query": "news"}},
        {"tool_name": "search", "params": {"query": "sports"}},
        {"tool_name": "search", "params": {"query": "tech"}},
    ])
    
    return results, parallel_results


if __name__ == "__main__":
    asyncio.run(example_usage())
