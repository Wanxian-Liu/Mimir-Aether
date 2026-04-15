"""
MimarAether Memory Provider 抽象层 V1.1

Round 2修复：
- 添加模拟外部Provider测试
- 完善prefetch和system_prompt_block实现
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderCapability(Enum):
    READ = "read"
    WRITE = "write"
    SEARCH = "search"
    CONTEXT = "context"
    TOOLS = "tools"


@dataclass
class ProviderInfo:
    name: str
    description: str
    capabilities: List[ProviderCapability]
    is_builtin: bool = False
    is_active: bool = False
    priority: int = 0


class MemoryProviderBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    def description(self) -> str:
        return ""
    
    @property
    def capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability.READ, ProviderCapability.WRITE]
    
    @property
    def is_builtin(self) -> bool:
        return False
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @abstractmethod
    def initialize(self, session_id: str, **kwargs) -> None:
        pass
    
    def system_prompt_block(self) -> str:
        return ""
    
    def prefetch(self, query: str, session_id: str = "") -> str:
        return ""
    
    def queue_prefetch(self, query: str, session_id: str = "") -> None:
        pass
    
    @abstractmethod
    def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        pass
    
    @abstractmethod
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        pass
    
    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        raise NotImplementedError(f"Provider {self.name} does not handle tool {tool_name}")
    
    def shutdown(self) -> None:
        pass
    
    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        pass
    
    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        pass
    
    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        return ""
    
    def on_memory_write(self, action: str, target: str, content: str) -> None:
        pass
    
    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            description=self.description,
            capabilities=self.capabilities,
            is_builtin=self.is_builtin,
            is_active=False,
            priority=0
        )


class BuiltinMemoryProvider(MemoryProviderBase):
    """内置内存Provider"""
    
    def __init__(self):
        self._session_id: str = ""
        self._initialized = False
        self._turn_count = 0
        self._memory_entries: List[Dict] = []
    
    @property
    def name(self) -> str:
        return "builtin"
    
    @property
    def description(self) -> str:
        return "内置记忆（MEMORY.md/USER.md）"
    
    @property
    def capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability.READ, ProviderCapability.WRITE, ProviderCapability.SEARCH, ProviderCapability.CONTEXT]
    
    @property
    def is_builtin(self) -> bool:
        return True
    
    def is_available(self) -> bool:
        return True
    
    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._initialized = True
        self._turn_count = 0
        self._memory_entries = kwargs.get("initial_memories", [])
        logger.info(f"BuiltinMemoryProvider initialized for {session_id}")
    
    def system_prompt_block(self) -> str:
        """返回内置内存的系统提示块"""
        if not self._memory_entries:
            return ""
        
        lines = ["## 持久记忆", ""]
        for entry in self._memory_entries[-10:]:  # 最近10条
            content = entry.get("content", "")
            entry_type = entry.get("type", "general")
            lines.append(f"- [{entry_type}] {content}")
        
        return "\n".join(lines)
    
    def prefetch(self, query: str, session_id: str = "") -> str:
        """基于查询返回相关记忆"""
        if not query or not self._memory_entries:
            return ""
        
        query_lower = query.lower()
        relevant = []
        
        for entry in self._memory_entries:
            content = entry.get("content", "").lower()
            if query_lower in content:
                relevant.append(entry)
        
        if not relevant:
            return ""
        
        lines = ["## 相关记忆", ""]
        for entry in relevant[:5]:  # 最多5条
            lines.append(f"- {entry.get('content', '')}")
        
        return "\n".join(lines)
    
    def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        self._turn_count += 1
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []
    
    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        self._turn_count = turn_number
    
    def add_memory(self, content: str, memory_type: str = "general") -> None:
        """添加记忆条目"""
        self._memory_entries.append({
            "content": content,
            "type": memory_type,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_turn_count(self) -> int:
        return self._turn_count
    
    def set_memories(self, memories: List[Dict]) -> None:
        self._memory_entries = memories


class ExternalMemoryProvider(MemoryProviderBase):
    """模拟外部内存Provider（如Honcho、Mem0等）"""
    
    def __init__(self, name: str = "honcho", description: str = "外部记忆服务"):
        self._name = name
        self._description = description
        self._session_id: str = ""
        self._turn_count = 0
        self._recalls: List[str] = []
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability.READ, ProviderCapability.CONTEXT]
    
    def is_available(self) -> bool:
        return True
    
    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._turn_count = 0
        self._recalls = []
        logger.info(f"{self.name} provider initialized for {session_id}")
    
    def system_prompt_block(self) -> str:
        return f"[{self.name} memory active]"
    
    def prefetch(self, query: str, session_id: str = "") -> str:
        """模拟召回"""
        if query:
            recall = f"[{self.name}] 相关: {query[:50]}..."
            self._recalls.append(recall)
            return recall
        return ""
    
    def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        self._turn_count += 1
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": f"{self.name}_search",
                "description": f"搜索{self.name}记忆库",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"}
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name == f"{self.name}_search":
            query = args.get("query", "")
            return f'{{"results": ["{query}相关的记忆1", "{query}相关的记忆2"]}}'
        raise NotImplementedError(f"{self.name} does not handle {tool_name}")


class MemoryProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, MemoryProviderBase] = {}
        self._active_provider: Optional[MemoryProviderBase] = None
        self._builtin: Optional[BuiltinMemoryProvider] = None
        self._session_id: str = ""
    
    def register(self, provider: MemoryProviderBase, activate: bool = False) -> None:
        if provider.name in self._providers:
            logger.warning(f"Provider {provider.name} already registered, replacing")
        
        self._providers[provider.name] = provider
        
        if activate:
            self.activate(provider.name)
        
        logger.info(f"Registered provider: {provider.name}" + (" [active]" if activate else ""))
    
    def activate(self, name: str) -> bool:
        if name not in self._providers:
            logger.error(f"Cannot activate: provider {name} not found")
            return False
        
        provider = self._providers[name]
        
        if not provider.is_available():
            logger.error(f"Cannot activate: provider {name} not available")
            return False
        
        if self._active_provider and self._active_provider.name != name:
            logger.info(f"Deactivating provider: {self._active_provider.name}")
        
        self._active_provider = provider
        
        if self._session_id:
            provider.initialize(self._session_id)
        
        logger.info(f"Activated provider: {name}")
        return True
    
    def deactivate(self) -> None:
        if self._active_provider:
            logger.info(f"Deactivating provider: {self._active_provider.name}")
            self._active_provider.shutdown()
            self._active_provider = None
    
    def initialize_session(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        
        if not self._builtin:
            self._builtin = BuiltinMemoryProvider()
        
        self._builtin.initialize(session_id, **kwargs)
        
        if self._active_provider:
            self._active_provider.initialize(session_id, **kwargs)
    
    def end_session(self, messages: List[Dict[str, Any]] = None) -> None:
        if self._builtin:
            if messages:
                self._builtin.on_session_end(messages)
            self._builtin.shutdown()
        
        if self._active_provider:
            if messages:
                self._active_provider.on_session_end(messages)
            self._active_provider.shutdown()
    
    def get_provider(self, name: str) -> Optional[MemoryProviderBase]:
        return self._providers.get(name)
    
    def get_active(self) -> Optional[MemoryProviderBase]:
        return self._active_provider
    
    def get_builtin(self) -> Optional[BuiltinMemoryProvider]:
        return self._builtin
    
    def list_providers(self) -> List[ProviderInfo]:
        infos = []
        
        if self._builtin:
            info = self._builtin.get_info()
            info.is_active = True
            info.priority = 9999
            infos.append(info)
        
        for provider in self._providers.values():
            info = provider.get_info()
            info.is_active = (provider.name == self._active_provider.name) if self._active_provider else False
            infos.append(info)
        
        return infos
    
    def get_context_for_prompt(self) -> str:
        parts = []
        
        if self._builtin:
            block = self._builtin.system_prompt_block()
            if block:
                parts.append(block)
        
        if self._active_provider:
            block = self._active_provider.system_prompt_block()
            if block:
                parts.append(block)
        
        return "\n\n".join(parts)
    
    def prefetch(self, query: str) -> str:
        results = []
        
        if self._builtin:
            result = self._builtin.prefetch(query, self._session_id)
            if result:
                results.append(result)
        
        if self._active_provider:
            result = self._active_provider.prefetch(query, self._session_id)
            if result:
                results.append(result)
        
        return "\n\n".join(results)
    
    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        
        if self._builtin:
            schemas.extend(self._builtin.get_tool_schemas())
        
        if self._active_provider:
            schemas.extend(self._active_provider.get_tool_schemas())
        
        return schemas


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("MemoryProvider V1.1 测试")
    print("=" * 60)
    
    # 创建注册表
    registry = MemoryProviderRegistry()
    
    # 初始化会话（带初始记忆）
    initial_memories = [
        {"content": "刘哥喜欢简洁直接的沟通风格", "type": "preference"},
        {"content": "MimirAether项目是核心项目", "type": "project"},
        {"content": "使用DeepSeek模型", "type": "config"},
    ]
    registry.initialize_session("test-session-456", initial_memories=initial_memories)
    print("\n✅ 会话初始化完成")
    
    # 列出providers
    providers = registry.list_providers()
    print(f"\nProvider列表 ({len(providers)}):")
    for p in providers:
        status = "⭐ builtin" if p.is_builtin else ("✅ active" if p.is_active else "  ")
        caps = ", ".join(c.value for c in p.capabilities)
        print(f"  {status} {p.name}: {p.description} [{caps}]")
    
    # 注册外部provider
    honcho = ExternalMemoryProvider("honcho", "Honcho记忆服务")
    registry.register(honcho, activate=True)
    print(f"\n✅ 外部Provider注册完成")
    
    # 测试预取
    print("\n[测试预取]")
    ctx = registry.get_context_for_prompt()
    print(f"上下文块: {ctx[:100] if ctx else '(空)'}")
    
    prefetch_result = registry.prefetch("MimirAether项目")
    print(f"预取结果: {prefetch_result[:100] if prefetch_result else '(空)'}")
    
    # 测试sync_turn
    print("\n[测试sync_turn]")
    registry.get_builtin().sync_turn("Hello", "Hi there!", "test-session-456")
    print(f"Turn count: {registry.get_builtin().get_turn_count()}")
    
    # 测试工具模式
    print("\n[测试工具模式]")
    tools = registry.get_all_tool_schemas()
    print(f"工具数量: {len(tools)}")
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    # 测试工具调用
    print("\n[测试工具调用]")
    result = honcho.handle_tool_call("honcho_search", {"query": "项目"})
    print(f"工具调用结果: {result}")
    
    # 测试provider切换
    print("\n[测试Provider切换]")
    registry.activate("builtin")
    print(f"当前Provider: {registry.get_active().name if registry.get_active() else '无'}")
    
    # 测试会话结束
    print("\n[测试会话结束]")
    registry.end_session()
    print("✅ 会话正常结束")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)