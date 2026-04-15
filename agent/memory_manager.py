"""
MimirAether Memory Manager - 记忆管理层

学习自Hermes memory_manager和memory_provider设计。

核心功能：
- MemoryProvider: 记忆提供者抽象基类
- MemoryManager: 记忆管理器，协调多个provider
- 支持内置记忆和外部记忆插件
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# MemoryProvider 抽象基类
# ============================================================================

class MemoryProvider(ABC):
    """
    记忆提供者抽象基类

    生命周期：
    1. initialize() - 会话初始化
    2. system_prompt_block() - 系统提示词
    3. prefetch() - 预取相关记忆
    4. sync_turn() - 同步一轮对话
    5. on_session_end() - 会话结束
    6. shutdown() - 关闭
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """短标识符，如 'builtin', 'user'"""

    @abstractmethod
    def is_available(self) -> bool:
        """返回True表示provider已配置好、可用"""

    @abstractmethod
    def initialize(self, session_id: str, **kwargs) -> None:
        """
        初始化会话

        session_id: 会话ID
        kwargs可能包含: hermes_home, platform, model等
        """

    def system_prompt_block(self) -> str:
        """
        返回要包含在系统提示词中的文本

        返回空字符串表示不贡献任何内容
        """
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """
        预取相关上下文

        在每次API调用前调用。返回要注入的格式化文本。
        """
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """
        队列后台预取（下次turn）

        在每轮结束后调用。结果将在下一轮的prefetch()中消费。
        """
        pass

    @abstractmethod
    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """
        将一轮对话同步到后端

        在每轮对话后调用
        """

    @abstractmethod
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        返回此provider暴露的工具schema列表

        每个schema遵循OpenAI函数调用格式：
        {"name": "...", "description": "...", "parameters": {...}}

        如果没有工具返回空列表
        """

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """处理工具调用"""
        return '{"error": "Not implemented"}'

    def shutdown(self) -> None:
        """清理关闭"""
        pass

    # -- 可选钩子 ----------------------------------------------------

    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        """每轮开始时调用"""
        pass

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """会话结束时调用"""
        pass

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """
        在上下文压缩前调用

        返回要包含在压缩摘要提示中的文本
        """
        return ""

    def on_delegation(self, task: str, result: str, *,
                      child_session_id: str = "", **kwargs) -> None:
        """
        当子代理完成时在父代理上调用

        task: 委托任务描述
        result: 子代理的最终响应
        child_session_id: 子代理的会话ID
        """
        pass

    def get_config_schema(self) -> List[Dict[str, Any]]:
        """
        返回此provider需要的配置字段

        每个字段格式：
        - key: 配置键名
        - description: 人类可读的描述
        - secret: 是否是密钥（默认False）
        - required: 是否必需（默认False）
        - default: 默认值（可选）
        - choices: 有效值列表（可选）
        - url: 凭证获取URL（可选）
        """
        return []

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """
        将非密钥配置写入provider的原生位置

        使用env vars的provider可以保持默认（no-op）
        """
        pass

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        """
        当内置记忆工具写入条目时调用

        action: 'add', 'replace', 或 'remove'
        target: 'memory' 或 'user'
        content: 条目内容
        """
        pass


# ============================================================================
# MemoryManager
# ============================================================================

class MemoryManager:
    """
    记忆管理器

    协调内置provider和最多一个外部provider
    """

    def __init__(self):
        self._providers: List[MemoryProvider] = []
        self._tool_to_provider: Dict[str, MemoryProvider] = {}
        self._has_external: bool = False

    # -- 注册 ----------------------------------------------------

    def add_provider(self, provider: MemoryProvider) -> None:
        """
        注册记忆provider

        内置provider（name="builtin"）总是被接受
        外部provider只能有一个
        """
        is_builtin = provider.name == "builtin"

        if not is_builtin:
            if self._has_external:
                existing = next(
                    (p.name for p in self._providers if p.name != "builtin"), "unknown"
                )
                logger.warning(
                    "Rejected memory provider '%s' — external provider '%s' is "
                    "already registered. Only one external memory provider is allowed.",
                    provider.name, existing,
                )
                return
            self._has_external = True

        self._providers.append(provider)

        # 索引工具名 → provider
        for schema in provider.get_tool_schemas():
            tool_name = schema.get("name", "")
            if tool_name and tool_name not in self._tool_to_provider:
                self._tool_to_provider[tool_name] = provider

        logger.info(
            "Memory provider '%s' registered (%d tools)",
            provider.name,
            len(provider.get_tool_schemas()),
        )

    @property
    def providers(self) -> List[MemoryProvider]:
        """所有已注册的provider"""
        return list(self._providers)

    def get_provider(self, name: str) -> Optional[MemoryProvider]:
        """按名称获取provider"""
        for p in self._providers:
            if p.name == name:
                return p
        return None

    # -- 系统提示词 -------------------------------------------------

    def build_system_prompt(self) -> str:
        """
        收集所有provider的系统提示词块

        返回合并的文本
        """
        blocks = []
        for provider in self._providers:
            try:
                block = provider.system_prompt_block()
                if block and block.strip():
                    blocks.append(block)
            except Exception as e:
                logger.warning(
                    "Memory provider '%s' system_prompt_block() failed: %s",
                    provider.name, e,
                )
        return "\n\n".join(blocks)

    # -- 预取/召回 -------------------------------------------------

    def prefetch_all(self, query: str, *, session_id: str = "") -> str:
        """
        从所有provider收集预取上下文

        返回合并的上下文文本
        """
        parts = []
        for provider in self._providers:
            try:
                result = provider.prefetch(query, session_id=session_id)
                if result and result.strip():
                    parts.append(result)
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' prefetch failed: %s",
                    provider.name, e,
                )
        return "\n\n".join(parts)

    def queue_prefetch_all(self, query: str, *, session_id: str = "") -> None:
        """为下一轮队列后台预取"""
        for provider in self._providers:
            try:
                provider.queue_prefetch(query, session_id=session_id)
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' queue_prefetch failed: %s",
                    provider.name, e,
                )

    # -- 同步 ----------------------------------------------------

    def sync_all(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """将一轮对话同步到所有provider"""
        for provider in self._providers:
            try:
                provider.sync_turn(user_content, assistant_content, session_id=session_id)
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' sync failed: %s",
                    provider.name, e,
                )

    # -- 会话生命周期 ----------------------------------------------

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """会话结束时调用"""
        for provider in self._providers:
            try:
                provider.on_session_end(messages)
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' on_session_end failed: %s",
                    provider.name, e,
                )

    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        """每轮开始时调用"""
        for provider in self._providers:
            try:
                provider.on_turn_start(turn_number, message, **kwargs)
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' on_turn_start failed: %s",
                    provider.name, e,
                )

    # -- 上下文压缩 -------------------------------------------------

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """在上下文压缩前收集provider贡献"""
        parts = []
        for provider in self._providers:
            try:
                result = provider.on_pre_compress(messages)
                if result and result.strip():
                    parts.append(result)
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' on_pre_compress failed: %s",
                    provider.name, e,
                )
        return "\n\n".join(parts)

    # -- 工具分发 -------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有provider的工具schema"""
        schemas = []
        for provider in self._providers:
            schemas.extend(provider.get_tool_schemas())
        return schemas

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """分发工具调用到对应provider"""
        provider = self._tool_to_provider.get(tool_name)
        if provider is None:
            return '{"error": "Unknown tool"}'

        try:
            return provider.handle_tool_call(tool_name, args, **kwargs)
        except Exception as e:
            logger.error(
                "Memory provider '%s' tool call failed: %s",
                provider.name, e,
            )
            return '{"error": "Tool execution failed"}'

    # -- 初始化/关闭 ----------------------------------------------

    def initialize_all(self, session_id: str, **kwargs) -> None:
        """初始化所有provider"""
        for provider in self._providers:
            try:
                provider.initialize(session_id, **kwargs)
            except Exception as e:
                logger.error(
                    "Memory provider '%s' initialize failed: %s",
                    provider.name, e,
                )

    def shutdown_all(self) -> None:
        """关闭所有provider"""
        for provider in self._providers:
            try:
                provider.shutdown()
            except Exception as e:
                logger.debug(
                    "Memory provider '%s' shutdown failed: %s",
                    provider.name, e,
                )


# ============================================================================
# 内置MemoryProvider示例
# ============================================================================

class BuiltinMemoryProvider(MemoryProvider):
    """
    内置记忆provider

    从workspace的MEMORY.md和USER.md加载记忆
    """

    def __init__(self, memory_path: str = None, user_path: str = None):
        self._memory_path = memory_path
        self._user_path = user_path
        self._session_id: str = ""

    @property
    def name(self) -> str:
        return "builtin"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id

    def system_prompt_block(self) -> str:
        blocks = []

        if self._memory_path:
            try:
                with open(self._memory_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        blocks.append(f"[Built-in Memory]\n{content}")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")

        if self._user_path:
            try:
                with open(self._user_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        blocks.append(f"[User Profile]\n{content}")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.warning(f"Failed to load user: {e}")

        return "\n\n".join(blocks)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        # BuiltinMemoryProvider不做主动写入
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        # BuiltinMemoryProvider不暴露工具
        return []


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Memory Manager 测试")
    print("=" * 60)

    # 测试1: BuiltinMemoryProvider
    print("\n[测试1] BuiltinMemoryProvider")
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Memory\n\nThis is test memory.")
        memory_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# User\n\nTest user profile.")
        user_path = f.name

    try:
        provider = BuiltinMemoryProvider(memory_path=memory_path, user_path=user_path)
        assert provider.name == "builtin"
        assert provider.is_available() == True
        provider.initialize("test-session")
        block = provider.system_prompt_block()
        assert "test memory" in block.lower() or "memory" in block.lower()
        print(f"  system_prompt_block: {len(block)} chars")
        print("  ✅ 通过")
    finally:
        os.unlink(memory_path)
        os.unlink(user_path)

    # 测试2: MemoryManager注册
    print("\n[测试2] MemoryManager注册")
    manager = MemoryManager()
    builtin = BuiltinMemoryProvider()
    manager.add_provider(builtin)
    assert len(manager.providers) == 1
    assert manager.get_provider("builtin") is builtin
    print(f"  providers: {[p.name for p in manager.providers]}")
    print("  ✅ 通过")

    # 测试3: 多个provider（只允许一个外部）
    print("\n[测试3] 多个provider限制")

    class ExternalProvider(MemoryProvider):
        @property
        def name(self) -> str:
            return "external"

        def is_available(self) -> bool:
            return True

        def initialize(self, session_id: str, **kwargs) -> None:
            pass

        def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
            pass

        def get_tool_schemas(self) -> List[Dict[str, Any]]:
            return []

    external1 = ExternalProvider()
    external2 = ExternalProvider()
    manager.add_provider(external1)
    # external2应该被拒绝
    assert len(manager.providers) == 2  # builtin + external1
    manager.add_provider(external2)  # 这应该被拒绝
    assert len(manager.providers) == 2  # 仍然只有2个
    print(f"  providers: {len(manager.providers)} (应为2)")
    print("  ✅ 通过")

    # 测试4: build_system_prompt
    print("\n[测试4] build_system_prompt")
    # 重新创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Memory\n\nThis is test memory.")
        memory_path2 = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# User\n\nTest user profile.")
        user_path2 = f.name

    try:
        manager2 = MemoryManager()
        provider2 = BuiltinMemoryProvider(memory_path=memory_path2, user_path=user_path2)
        manager2.add_provider(provider2)
        prompt = manager2.build_system_prompt()
        assert len(prompt) > 0
        print(f"  system_prompt: {len(prompt)} chars")
        print("  ✅ 通过")
    finally:
        os.unlink(memory_path2)
        os.unlink(user_path2)

    # 测试5: sync_all
    print("\n[测试5] sync_all")

    class CountingProvider(MemoryProvider):
        call_count = 0

        @property
        def name(self) -> str:
            return "counting"

        def is_available(self) -> bool:
            return True

        def initialize(self, session_id: str, **kwargs) -> None:
            pass

        def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
            CountingProvider.call_count += 1

        def get_tool_schemas(self) -> List[Dict[str, Any]]:
            return []

    CountingProvider.call_count = 0  # 重置
    manager3 = MemoryManager()
    cp = CountingProvider()
    manager3.add_provider(cp)
    manager3.sync_all("user", "assistant")
    assert CountingProvider.call_count == 1
    print(f"  sync_all调用次数: {CountingProvider.call_count}")
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)