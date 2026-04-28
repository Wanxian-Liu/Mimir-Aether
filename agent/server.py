"""Agent Server - Core agent orchestration server."""
import asyncio
import logging
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Agent configuration."""
    name: str = "default"
    model: str = "claude-3-5-sonnet"
    max_iterations: int = 100
    timeout: int = 300
    tools: list[str] = field(default_factory=list)
    system_prompt: Optional[str] = None


@dataclass
class AgentContext:
    """Agent execution context."""
    session_id: str
    user_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE


class AgentServer:
    """Core agent orchestration server."""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.contexts: dict[str, AgentContext] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        logger.info(f"AgentServer initialized: {self.config.name}")
    
    async def start(self) -> None:
        """Start the agent server."""
        logger.info("Starting agent server...")
        await asyncio.sleep(0.1)
        logger.info("Agent server started")
    
    async def stop(self) -> None:
        """Stop the agent server."""
        logger.info("Stopping agent server...")
        for task in self._running_tasks.values():
            task.cancel()
        await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        self._running_tasks.clear()
        logger.info("Agent server stopped")


@dataclass
class Message:
    """Agent message."""
    role: str  # user, assistant, system, tool
    content: str
    metadata: dict = field(default_factory=dict)


async def create_context(self, session_id: str, user_id: Optional[str] = None) -> AgentContext:
    """Create a new agent context."""
    ctx = AgentContext(session_id=session_id, user_id=user_id)
    self.contexts[session_id] = ctx
    logger.info(f"Created context for session: {session_id}")
    return ctx


async def get_context(self, session_id: str) -> Optional[AgentContext]:
    """Get existing context."""
    return self.contexts.get(session_id)


async def delete_context(self, session_id: str) -> bool:
    """Delete a context."""
    if session_id in self.contexts:
        del self.contexts[session_id]
        logger.info(f"Deleted context: {session_id}")
        return True
    return False


async def add_message(self, session_id: str, role: str, content: str, metadata: dict = None) -> bool:
    """Add a message to context history."""
    ctx = await self.get_context(session_id)
    if not ctx:
        return False
    msg = Message(role=role, content=content, metadata=metadata or {})
    ctx.history.append({"role": role, "content": content, "metadata": msg.metadata})
    return True


class ToolResult:
    """Result from tool execution."""
    def __init__(self, name: str, success: bool, result: Any = None, error: str = None):
        self.name = name
        self.success = success
        self.result = result
        self.error = error


class ToolRegistry:
    """Registry for agent tools."""
    
    def __init__(self):
        self._tools: dict[str, callable] = {}
    
    def register(self, name: str, func: callable) -> None:
        """Register a tool function."""
        self._tools[name] = func
        logger.debug(f"Registered tool: {name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a registered tool."""
        if name not in self._tools:
            return ToolResult(name=name, success=False, error=f"Tool not found: {name}")
        try:
            func = self._tools[name]
            if asyncio.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)
            return ToolResult(name=name, success=True, result=result)
        except Exception as e:
            logger.error(f"Tool execution error: {name} - {e}")
            return ToolResult(name=name, success=False, error=str(e))
    
    def list_tools(self) -> list[str]:
        """List all registered tools."""
        return list(self._tools.keys())


class AgentExecutor:
    """Handles agent execution logic."""
    
    def __init__(self, server: "AgentServer"):
        self.server = server
        self.tools = ToolRegistry()
    
    async def execute_turn(self, session_id: str, user_input: str) -> dict[str, Any]:
        """Execute a single agent turn."""
        ctx = await self.server.get_context(session_id)
        if not ctx:
            ctx = await self.server.create_context(session_id)
        
        ctx.status = AgentStatus.RUNNING
        await self.server.add_message(session_id, "user", user_input)
        
        # Placeholder for LLM call
        response = f"Processing: {user_input}"
        
        await self.server.add_message(session_id, "assistant", response)
        ctx.status = AgentStatus.COMPLETED
        
        return {"response": response, "status": ctx.status.value}
    
    async def run_loop(self, session_id: str, max_iterations: int = None) -> dict[str, Any]:
        """Run agent loop until completion or max iterations."""
        max_iter = max_iterations or self.server.config.max_iterations
        iterations = 0
        results = []
        
        while iterations < max_iter:
            iterations += 1
            result = await self.execute_turn(session_id, f"iteration_{iterations}")
            results.append(result)
            
            if result["status"] == AgentStatus.COMPLETED.value:
                break
        
        return {"iterations": iterations, "results": results}


# Extend AgentServer with execution methods
async def process_message(self, session_id: str, message: str) -> dict[str, Any]:
    """Process a user message."""
    ctx = self.contexts.get(session_id)
    if not ctx:
        ctx = await self.create_context(session_id)
    
    await self.add_message(session_id, "user", message)
    ctx.status = AgentStatus.RUNNING
    
    # TODO: Integrate with LLM
    response = f"Echo: {message}"
    
    await self.add_message(session_id, "assistant", response)
    ctx.status = AgentStatus.COMPLETED
    
    return {"session_id": session_id, "response": response, "status": ctx.status.value}


async def get_history(self, session_id: str) -> list[dict]:
    """Get message history for session."""
    ctx = self.contexts.get(session_id)
    return ctx.history if ctx else []


def get_stats(self) -> dict[str, Any]:
    """Get server statistics."""
    return {
        "total_sessions": len(self.contexts),
        "active_tasks": len(self._running_tasks),
        "config": {
            "name": self.config.name,
            "model": self.config.model,
            "max_iterations": self.config.max_iterations,
        }
    }


if __name__ == "__main__":
    async def main():
        """Entry point."""
        logging.basicConfig(level=logging.INFO)
        
        server = AgentServer(AgentConfig(name="test-agent"))
        await server.start()
        
        # Demo
        result = await server.process_message("demo-session", "Hello!")
        print(f"Result: {result}")
        print(f"Stats: {server.get_stats()}")
        
        await server.stop()
    
    asyncio.run(main())
