"""
MimirAether Context Engine - 抽象基类

学习自Hermes context_engine.py设计。

核心功能：
- 定义上下文引擎的统一接口
- 支持插件化的上下文压缩策略
- 支持第三方引擎（如LCM）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ============================================================================
# ContextEngine 抽象基类
# ============================================================================

class ContextEngine(ABC):
    """
    所有上下文引擎必须实现的基类

    生命周期：
    1. on_session_start() - 会话开始时调用
    2. update_from_response() - 每次API响应后调用
    3. should_compress() - 每轮检查是否需要压缩
    4. compress() - 当should_compress()返回True时调用
    5. on_session_end() - 会话真正结束时调用（不是每轮）
    """

    # -- 身份属性 ----------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """短标识符，如 'compressor', 'lcm' """

    # -- Token状态（供core_loop读取） --------------------------------

    last_prompt_tokens: int = 0
    last_completion_tokens: int = 0
    last_total_tokens: int = 0
    threshold_tokens: int = 0
    context_length: int = 0
    compression_count: int = 0

    # -- 压缩参数 ----------------------------------------------------

    threshold_percent: float = 0.75  # 75%阈值
    protect_first_n: int = 3        # 保护前N条消息
    protect_last_n: int = 6         # 保护后N条消息

    # -- 核心接口 ----------------------------------------------------

    @abstractmethod
    def update_from_response(self, usage: Dict[str, Any]) -> None:
        """
        从API响应更新token使用情况

        每次LLM调用后传入usage字典
        """

    @abstractmethod
    def should_compress(self, prompt_tokens: int = None) -> bool:
        """返回True表示本轮应该触发压缩"""

    @abstractmethod
    def compress(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int = None,
        focus_topic: str = None,
    ) -> List[Dict[str, Any]]:
        """
        压缩消息列表并返回新的消息列表

        引擎接收完整消息列表，返回（可能更短的）列表

        Args:
            focus_topic: 可选主题字符串，来自手动 ``/compress <focus>``。
                支持定向压缩的引擎应优先保留与此主题相关的信息。
                不支持的引擎可忽略此参数。
        """

    # -- 可选：预检 ----------------------------------------------------

    def should_compress_preflight(self, messages: List[Dict[str, Any]]) -> bool:
        """
        API调用前的快速预检（尚未有真实token计数）

        默认返回False，子类可覆盖实现廉价估算
        """
        return False

    def has_content_to_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """
        快速检查：messages 中是否有可以压缩的内容？

        用于 gateway ``/compress`` 命令的预检哨兵 —
        返回 False 让 gateway 可以报告"尚无内容可压缩"而不调用 LLM。

        默认返回 True（始终尝试）。有能力廉价内省自己的 head/tail
        边界的引擎应覆盖此方法，在 transcript 仍完全受保护时返回 False。
        """
        return True

    # -- 可选：会话生命周期 -------------------------------------------

    def on_session_start(self, session_id: str, **kwargs) -> None:
        """
        新会话开始时调用

        可用于加载持久化状态（DAG等）
        kwargs可能包含hermes_home, platform, model等
        """
        pass

    def on_session_end(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        会话真正结束时调用（CLI退出、/reset、gateway会话过期）

        NOT每轮调用——只在会话真正结束时调用
        """
        pass

    def on_session_reset(self) -> None:
        """/new或/reset时调用，重置会话状态"""
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0

    # -- 可选：工具 ----------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        返回引擎提供给agent的工具schema列表

        默认返回空列表（无工具）
        LCM引擎会返回lcm_grep, lcm_describe, lcm_expand等schema
        """
        return []

    def handle_tool_call(self, name: str, args: Dict[str, Any], **kwargs) -> str:
        """
        处理来自agent的工具调用

        只对get_tool_schemas()返回的工具名调用
        必须返回JSON字符串
        """
        import json
        return json.dumps({"error": f"Unknown context engine tool: {name}"})

    # -- 可选：状态/显示 -------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        返回用于显示/日志的状态字典

        默认返回core_loop期望的标准字段
        """
        return {
            "last_prompt_tokens": self.last_prompt_tokens,
            "threshold_tokens": self.threshold_tokens,
            "context_length": self.context_length,
            "usage_percent": (
                min(100, self.last_prompt_tokens / self.context_length * 100)
                if self.context_length else 0
            ),
            "compression_count": self.compression_count,
        }

    # -- 可选：模型切换支持 ----------------------------------------

    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
    ) -> None:
        """
        用户切换模型或激活fallback时调用

        默认更新context_length并从threshold_percent重新计算threshold_tokens
        子类可覆盖以实现更多逻辑（如重新计算DAG budgets、切换summary模型等）
        """
        self.context_length = context_length
        self.threshold_tokens = int(context_length * self.threshold_percent)


# ============================================================================
# 注册表
# ============================================================================

class ContextEngineRegistry:
    """
    上下文引擎注册表

    管理所有已注册的上下文引擎，支持通过名称访问
    """

    def __init__(self):
        self._engines: Dict[str, ContextEngine] = {}
        self._default_name: str = "compressor"

    def register(self, engine: ContextEngine) -> None:
        """注册一个上下文引擎"""
        self._engines[engine.name] = engine

    def get(self, name: str) -> Optional[ContextEngine]:
        """获取指定名称的引擎"""
        return self._engines.get(name)

    def list_engines(self) -> List[str]:
        """列出所有已注册的引擎名称"""
        return list(self._engines.keys())

    @property
    def default(self) -> ContextEngine:
        """获取默认引擎"""
        return self._engines.get(self._default_name)

    def set_default(self, name: str) -> None:
        """设置默认引擎"""
        if name not in self._engines:
            raise ValueError(f"Unknown engine: {name}")
        self._default_name = name


# 全局注册表实例
_global_registry: Optional[ContextEngineRegistry] = None


def get_engine_registry() -> ContextEngineRegistry:
    """获取全局引擎注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ContextEngineRegistry()
    return _global_registry


def register_engine(engine: ContextEngine) -> None:
    """注册引擎到全局注册表"""
    get_engine_registry().register(engine)


# ============================================================================
# 工厂函数
# ============================================================================

def create_context_engine(
    engine_name: str = "compressor",
    **kwargs,
) -> ContextEngine:
    """
    创建上下文引擎的工厂函数

    Args:
        engine_name: 引擎名称，默认"compressor"
        **kwargs: 传递给引擎构造函数的参数
    """
    registry = get_engine_registry()
    engine = registry.get(engine_name)

    if engine is None:
        raise ValueError(f"Unknown context engine: {engine_name}")

    return engine


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Context Engine 测试")
    print("=" * 60)

    # 测试1: ContextEngineRegistry
    print("\n[测试1] ContextEngineRegistry")
    registry = ContextEngineRegistry()

    class DummyEngine(ContextEngine):
        @property
        def name(self) -> str:
            return "dummy"

        def update_from_response(self, usage: Dict[str, Any]) -> None:
            pass

        def should_compress(self, prompt_tokens: int = None) -> bool:
            return False

        def compress(
            self,
            messages: List[Dict[str, Any]],
            current_tokens: int = None,
        ) -> List[Dict[str, Any]]:
            return messages

    dummy = DummyEngine()
    registry.register(dummy)
    assert registry.get("dummy") is dummy
    assert "dummy" in registry.list_engines()
    print(f"  注册引擎: {registry.list_engines()}")
    print("  ✅ 通过")

    # 测试2: 注册表默认引擎
    print("\n[测试2] 注册表默认引擎")
    registry2 = ContextEngineRegistry()
    assert registry2.default is None  # 无默认引擎时为None

    class CompressorEngine(ContextEngine):
        @property
        def name(self) -> str:
            return "compressor"

        def update_from_response(self, usage: Dict[str, Any]) -> None:
            pass

        def should_compress(self, prompt_tokens: int = None) -> bool:
            return False

        def compress(
            self,
            messages: List[Dict[str, Any]],
            current_tokens: int = None,
        ) -> List[Dict[str, Any]]:
            return messages

    compressor = CompressorEngine()
    registry2.register(compressor)
    assert registry2.default is compressor
    print("  ✅ 通过")

    # 测试3: create_context_engine
    print("\n[测试3] create_context_engine")
    # 需要先注册一个引擎
    register_engine(dummy)
    engine = create_context_engine("dummy")
    assert engine is dummy
    print("  ✅ 通过")

    # 测试4: get_engine_registry
    print("\n[测试4] get_engine_registry单例")
    reg1 = get_engine_registry()
    reg2 = get_engine_registry()
    assert reg1 is reg2  # 同一实例
    print("  ✅ 通过")

    # 测试5: ContextEngine属性
    print("\n[测试5] ContextEngine属性")
    dummy.context_length = 128000
    dummy.threshold_percent = 0.75
    dummy.update_model("gpt-4", 128000)
    assert dummy.context_length == 128000
    assert dummy.threshold_tokens == 96000  # 128000 * 0.75
    print(f"  threshold_tokens: {dummy.threshold_tokens}")
    print("  ✅ 通过")

    # 测试6: get_status
    print("\n[测试6] get_status")
    dummy.last_prompt_tokens = 50000
    dummy.compression_count = 2
    status = dummy.get_status()
    print(f"  status: {status}")
    assert status["last_prompt_tokens"] == 50000
    assert status["compression_count"] == 2
    assert 38 < status["usage_percent"] < 40  # 50000/128000*100 ≈ 39.06
    print("  ✅ 通过")

    # 测试7: on_session_reset
    print("\n[测试7] on_session_reset")
    dummy.last_prompt_tokens = 50000
    dummy.compression_count = 5
    dummy.on_session_reset()
    assert dummy.last_prompt_tokens == 0
    assert dummy.compression_count == 0
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)