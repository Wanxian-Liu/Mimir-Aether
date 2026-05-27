"""
ConfigMixin — Agent config: API keys, model resolution, system prompt, budget, fallback.

Extracted from MimirAetherAgent (agent/core_loop.py) as part of d4 split.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from . import prompt_builder
from .credential_pool import CredentialPool, create_credential
from .smart_model_routing import resolve_turn_route
from .skill_funcs import SKILL_MANAGE_SCHEMA, SKILL_TOOL_SCHEMAS

import tools.registry as _tool_registry_module

if TYPE_CHECKING:
    from agent.core_loop import MimirAetherAgent

logger = logging.getLogger(__name__)

class ConfigMixin:
    """Agent config: API keys, model resolution, system prompt, budget, fallback.

    Designed to be mixed into MimirAetherAgent.
    """
    def _init_credential_pool(self) -> None:
        """初始化凭证池"""
        # 收集可用凭证
        entries = []

        # 从环境变量加载 DeepSeek
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if deepseek_key:
            entries.append(create_credential("deepseek", deepseek_key, "DeepSeek Primary"))

        # 从环境变量加载 MiniMax
        minimax_key = os.environ.get("MINIMAX_API_KEY", "").strip()
        if minimax_key:
            entries.append(create_credential("minimax", minimax_key, "MiniMax Primary"))

        # 从环境变量加载 OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            entries.append(create_credential("openai", openai_key, "OpenAI Primary"))

        # 从环境变量加载 Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if anthropic_key:
            entries.append(create_credential("anthropic", anthropic_key, "Anthropic Primary"))

        if entries:
            self._credential_pool = CredentialPool(self.model, entries, strategy="round_robin")
            logger.info(f"Credential pool initialized with {len(entries)} entries")
        else:
            logger.debug("No credentials found for pool, using environment variables directly")

    # ============================================================================
    # 预算和恢复状态（学习自Hermes）
    # ============================================================================
    
    def get_budget_warning(self) -> str:
        """获取当前预算警告级别"""
        level = self.budget.get_warning_level()
        remaining = asyncio.run(self.budget.get_remaining())
        total = self.budget.max_total
        pct = remaining / total * 100
        return f"[{level.value.upper()}] {remaining}/{total} ({pct:.1f}% remaining)"
    
    async def check_and_warn_budget(self) -> bool:
        """
        检查预算并发出警告
        
        Returns:
            是否应该继续执行
        """
        if self.budget.should_warn():
            warning = self.get_budget_warning()
            logger.warning(f"Iteration budget warning: {warning}")
            if self.status_callback:
                await self._emit_status(f"⚠️ {warning}")
            return self.budget.is_safe_to_continue()
        return True
    
    def _get_api_key(self) -> str:
        """获取当前模型的API key"""
        # Moonshot/Kimi系列 使用MOONSHOT_API_KEY环境变量
        if self.model.startswith("kimi-k2") or self.model.startswith("moonshot"):
            return os.environ.get("MOONSHOT_API_KEY", "")

        # DeepSeek优先使用DEEPSEEK_API_KEY，fallback到OPENROUTER_API_KEY（用于OpenRouter上的DeepSeek模型）
        if "deepseek" in self.model.lower():
            return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")

        # 优先从凭证池获取
        if self._credential_pool:
            selected = self._credential_pool.current()
            if selected:
                return selected.runtime_api_key

        # fallback到环境变量
        model_lower = self.model.lower()
        if "deepseek" in model_lower:
            return os.environ.get("DEEPSEEK_API_KEY", "")
        elif "minimax" in model_lower:
            return os.environ.get("MINIMAX_API_KEY", "")
        elif "anthropic" in model_lower or "claude" in model_lower:
            return os.environ.get("ANTHROPIC_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
        elif "openai" in model_lower or "gpt" in model_lower:
            return os.environ.get("OPENAI_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
        else:
            return os.environ.get("DEEPSEEK_API_KEY", "")

    def _get_model_base_url(self) -> str:
        """获取当前模型的API base URL"""
        # Moonshot/Kimi系列 使用Moonshot API
        if self.model.startswith("kimi-k2") or self.model.startswith("moonshot"):
            return "https://api.moonshot.cn"  # 不要加/v1,会在API调用时拼接

        model_lower = self.model.lower()
        if "deepseek" in model_lower:
            return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        elif "minimax" in model_lower:
            return os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com")
        elif "anthropic" in model_lower or "claude" in model_lower:
            return os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        elif "openai" in model_lower or "gpt" in model_lower:
            return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        else:
            return "https://api.deepseek.com"

    def _guess_provider(self, model_name: str) -> str:
        """Guess provider from model name for routing purposes."""
        ml = model_name.lower()
        if any(x in ml for x in ("deepseek", "kimi", "moonshot")):
            return "deepseek"
        if any(x in ml for x in ("anthropic", "claude")):
            return "anthropic"
        if any(x in ml for x in ("openai", "gpt")):
            return "openai"
        return "deepseek"

    def _load_smart_routing_config(self) -> dict:
        """Load smart routing config from config.yaml or env."""
        try:
            import yaml as _y
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent / "config.yaml"
            if cfg_path.exists():
                with open(cfg_path, encoding="utf-8") as _f:
                    cfg = _y.safe_load(_f) or {}
                return cfg.get("smart_model_routing", {}) or {}
        except Exception:
            pass
        return {}

    def _resolve_api_config(self, model_name: str = None, user_message: str = None) -> Dict[str, Any]:
        """
        解析API配置(统一方法)

        Returns:
            dict with keys: api_key, base_url, is_anthropic, model_name, route_label (optional)
        """
        if model_name is None:
            model_name = self.model

        # Smart routing: 检查是否可以使用便宜模型
        route_label = None
        intent_pred = getattr(self, "_intent_prediction", None)
        if intent_pred and getattr(intent_pred, "block_cheap_route", False):
            return {
                "api_key": self._get_api_key(),
                "base_url": self._get_model_base_url(),
                "is_anthropic": any(
                    x in model_name.lower() for x in ["anthropic", "claude"]
                ),
                "model_name": model_name,
                "route_label": "intent_predictor: block cheap route",
            }
        if user_message:
            try:
                routing_cfg = getattr(self, '_smart_routing_config', None)
                if routing_cfg is None:
                    routing_cfg = self._load_smart_routing_config()
                    self._smart_routing_config = routing_cfg

                primary = {
                    "model": model_name,
                    "provider": self._guess_provider(model_name),
                    "api_key": self._get_api_key(),
                    "base_url": self._get_model_base_url(),
                }
                route = resolve_turn_route(user_message, routing_cfg, primary)
                if route.get("is_cheap"):
                    logger.info(
                        "Smart route: %s → %s (%s)",
                        model_name, route["model"], route.get("label", "")
                    )
                    route_label = route.get("label")
                    model_name = route["model"]
                    # Override provider-specific config for cheap model
                    api_key = route["runtime"].get("api_key") or self._get_api_key()
                    base_url = route["runtime"].get("base_url") or self._get_model_base_url()
                    is_anthropic = any(x in model_name.lower() for x in ["anthropic", "claude"])
                    return {
                        "api_key": api_key,
                        "base_url": base_url,
                        "is_anthropic": is_anthropic,
                        "model_name": model_name,
                        "route_label": route_label,
                    }
            except Exception as e:
                logger.debug("Smart routing skipped: %s", e)

        api_key = self._get_api_key()
        base_url = self._get_model_base_url()

        # 检测是否为Anthropic模型
        is_anthropic = any(x in model_name.lower() for x in ["anthropic", "claude"])

        return {
            "api_key": api_key,
            "base_url": base_url,
            "is_anthropic": is_anthropic,
            "model_name": model_name,
            "route_label": route_label,
        }

    def _build_system_prompt(self) -> str:
        """使用prompt_builder构建完整的系统提示"""
        try:
            # 获取可用工具列表
            available_tools = set(_tool_registry_module.registry.get_all_tool_names())

            # MimirAether的skills目录
            mimir_root = Path(__file__).parent.parent
            skills_dir = str(mimir_root / "skills")

            # 使用prompt_builder构建系统提示
            system_prompt = prompt_builder.build_system_prompt(
                model=self.model,
                cwd=os.getcwd(),
                available_tools=available_tools,
                platform=self.platform,
                include_skills=True,
                include_context=True,
                skills_dirs=[skills_dir],
            )

            return system_prompt if system_prompt else self._default_system_prompt()
        except Exception as e:
            logger.warning(f"Failed to build system prompt with prompt_builder: {e}")
            return self._default_system_prompt()

    def _build_system_prompt_parts(self) -> dict:
        """构建分层系统提示，用于跨会话前缀缓存。
        
        返回 {"stable": str, "context": str, "volatile": str}
        仅当模型支持 Anthropic prefix cache 时有意义。
        """
        try:
            available_tools = set(_tool_registry_module.registry.get_all_tool_names())
            mimir_root = Path(__file__).parent.parent
            skills_dir = str(mimir_root / "skills")

            return prompt_builder.build_system_prompt_parts(
                model=self.model,
                cwd=os.getcwd(),
                available_tools=available_tools,
                platform=self.platform,
                include_skills=True,
                include_context=True,
                skills_dirs=[skills_dir],
            )
        except Exception as e:
            logger.warning(f"Failed to build system prompt parts: {e}")
            # 回退：把整个system_prompt当stable
            return {"stable": self.system_prompt, "context": "", "volatile": ""}

    def _supports_prefix_cache(self, model_name: str = None, base_url: str = None, is_anthropic: bool = None) -> bool:
        """判断当前配置是否支持跨会话 prefix cache。
        
        条件：Claude + (Anthropic原生API 或 OpenRouter/Nous)
        """
        m = (model_name or self.model or "").lower()
        if "claude" not in m:
            return False
        
        if is_anthropic is not None:
            return is_anthropic
        
        # 从API配置推断
        api_config = self._resolve_api_config(m)
        return api_config.get("is_anthropic", False)

    def _register_builtin_tools(self):
        """注册内置工具（Hermes 模式：工具通过模块导入自注册）

        工具现在通过 tools/ 目录下各模块的 registry.register() 调用自动注册。
        只需导入模块即可触发注册。Skill 工具仍需手动注册。
        """
        import sys
        from pathlib import Path

        # 将MimirAether根目录添加到path
        mimir_root = Path(__file__).parent.parent
        if str(mimir_root) not in sys.path:
            sys.path.insert(0, str(mimir_root))

        # ── 导入工具模块（自注册到 tools.registry.registry） ──
        builtin_count = 0
        mimircore_count = 0
        try:
            import tools.builtin  # noqa: F401 - 导入即触发 registry.register()
            builtin_count = len([e for e in _tool_registry_module.registry._tools.values()
                                if e.toolset in ("file", "code_execution", "web")])
        except ImportError as e:
            logger.warning(f"Failed to import builtin tools: {e}")

        try:
            import tools.mimircore_tool  # noqa: F401 - 导入即触发 registry.register()
            mimircore_count = len([e for e in _tool_registry_module.registry._tools.values()
                                  if e.toolset == "mimircore"])
        except ImportError as e:
            logger.warning(f"Failed to import mimircore tools: {e}")

        logger.info(f"Self-registered {builtin_count} builtin + {mimircore_count} mimircore tools")

        # ── 注册Skill工具（skill_view, skills_list, skill_manage） ──
        try:
            from skills.skills_loader import skill_view as _skill_view_func, skills_list as _skills_list_func
            from skills.skills_loader import skill_manage as _skill_manage_func

            # 直接注册到 tools.registry.registry（Hermes 模式，toolset="skills"）
            _tool_registry_module.registry.register(
                name="skill_view",
                toolset="skills",
                schema=SKILL_TOOL_SCHEMAS["skill_view"],
                handler=lambda args, **kw: _skill_view_func(**args),
            )
            _tool_registry_module.registry.register(
                name="skills_list",
                toolset="skills",
                schema=SKILL_TOOL_SCHEMAS["skills_list"],
                handler=lambda args, **kw: _skills_list_func(**args),
            )
            _tool_registry_module.registry.register(
                name="skill_manage",
                toolset="skills",
                schema=SKILL_MANAGE_SCHEMA,
                handler=lambda args, **kw: _skill_manage_func(**args),
            )

            logger.info("Registered skill tools: skill_view, skills_list, skill_manage")
        except ImportError as e:
            logger.warning(f"Failed to import skill tools: {e}")

    def _default_system_prompt(self) -> str:
        """默认系统提示"""
        return """You are MimirAether, an AI assistant powered by advanced reasoning and tool execution capabilities.

Core capabilities:
- Natural language understanding and generation
- Tool execution for various tasks
- Code writing, debugging, and execution
- File operations and system tasks
- Web search and information retrieval
- Memory management across sessions

## Tool Calling Rules (CRITICAL)

When calling tools, you MUST use the exact parameter names defined in the tool schema:

- execute_code: parameter is `code` NOT `command`
- write_file: parameters are `path` and `content`
- read_file: parameter is `path`
- get_env: parameter is `key` (optional `default`)
- web_search: parameter is `query`

You must strictly follow the parameter names in the schema. Do not use alternative names or make assumptions about parameter names.

You can call tools to accomplish tasks. Always provide clear, accurate responses.

## Self-Evolution Guide (When asked to evolve/improve)

When given an evolution task, you MUST:
1. Read the relevant code files first
2. Make ONE small, safe change to the code
3. Use write_file to save the change
4. Report what you changed and why

Small progress is good! Even one line changed is real progress.
Do not just report - you must modify files to show progress.

Do not be afraid of mistakes - they can be fixed. Report your changes."""

    def _try_activate_fallback(self) -> bool:
        """
        尝试激活Fallback模型

        学习自Hermes fallback机制:
        - 当主模型API失败时,尝试使用fallback模型
        - 需要配置fallback_model
        """
        if not self.fallback_model:
            return False

        if self._fallback_activated:
            logger.debug("Fallback already activated, not trying again")
            return False

        try:
            fallback = self.fallback_model
            self.model = fallback.get("model", self.model)
            self._fallback_activated = True
            self._emit_status(f"🔄 Activating fallback model: {self.model}")
            logger.info(f"Fallback activated: {self.model}")
            return True
        except Exception as e:
            logger.warning(f"Failed to activate fallback: {e}")
            return False

    def _restore_primary_runtime(self) -> None:
        """
        恢复主运行时(Fallback后)

        学习自Hermes:
        - 在新的对话轮次开始时,如果上次使用了fallback,尝试恢复主模型
        - 只有当_fallback_activated为True时才恢复
        """
        if not self._fallback_activated:
            return

        if self._primary_model and self.model != self._primary_model:
            self.model = self._primary_model
            self._fallback_activated = False
            self._emit_status(f"✅ Restored primary model: {self.model}")
            logger.info(f"Primary runtime restored: {self.model}")


# 导出的类和函数
__all__ = [
    "MimirAetherAgent",
    "Message",
    "MessageRole",
    "ToolCall",
    "ToolResult",
    "Plan",
    "ExecutionResult",
    "IterationBudget",
    "ToolRegistry",
]


# 技能函数已迁移到 agent/skill_funcs.py
# 导入已在上方完成，保持向后兼容
