"""
MimirAgentLoop - Pure Agent Execution Engine

Extracted from MimirAetherAgent.run_conversation() following the Hermes
microkernel pattern. This class is a pure execution engine:

  - Receives: model caller, tool schemas, tool dispatcher, messages
  - Runs: the tool-calling loop (standard OpenAI-spec)
  - Returns: AgentResult with full metadata

It does NOT manage models, credentials, system prompts, or tool registration.
Those are MimirAetherAgent's responsibility (the configuration layer).

Key design from Hermes:
  - ThreadPoolExecutor for sync tool calls (async bridge)
  - Persistent event loops via async_bridge.py
  - AgentResult with ToolError for structured error collection
  - Reasoning extraction across provider formats
  - Fallback <tool_call> parser
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable

from .async_bridge import get_tool_executor
from .conversation_nudges import (
    maybe_memory_nudge_message,
    maybe_skill_nudge_message,
    maybe_parallel_read_nudge,
)
from .intent_action_guard import (
    MAX_INTENT_NUDGES,
    build_nudge_message,
    guard_enabled,
    should_block_text_only_finish,
)
from .intent_predictor import (
    predictor_enabled as intent_predictor_enabled,
    predict_and_format as intent_predict_and_format,
)
from .search_first_guard import (
    MAX_SEARCH_FIRST_NUDGES,
    build_nudge_message as build_search_first_nudge,
    cross_session_requires_search_first,
    guard_enabled as search_first_guard_enabled,
    last_user_text,
    session_search_satisfied_since_last_user,
    should_block_text_only_finish as should_block_search_first_finish,
)
from .skill_scenario_router import (
    build_skill_route_nudge,
    should_inject_skill_route_nudge,
)
# WM imports — archived 2026-08-03 (docs/archive/world-model-20260803).
# Defensive import: modules are archived, so guard against ImportError so the
# agent loop keeps working (surprise flow disabled per WM discussion consensus).
try:
    from .world_model_spike import is_wm_predictor_enabled, predict as wm_predict
    from .wm_voe_learning import append_surprise_event
except ImportError:
    is_wm_predictor_enabled = lambda: False
    wm_predict = lambda *a, **k: None
    append_surprise_event = lambda *a, **k: None
from .verify_before_report_guard import (
    build_nudge_message as build_verify_nudge,
    guard_enabled as verify_guard_enabled,
    should_block_finish as should_block_verify_finish,
)
from .task_state import TaskState  # task_state（四方共识，2026-08-05）
MAX_VERIFY_NUDGES = 3  # verify guard最大nudge次数（修复：防freeze loop——对齐MAX_INTENT_NUDGES模式）
# OC-01: auto_retrospective archived
# from .auto_retrospective import enabled as retro_enabled, record as record_retro
# 统一类型: 从 types.py 导入 (Phase 3 M1)
from .types import AgentLoopToolError as ToolError, AgentLoopResult as AgentResult

logger = logging.getLogger(__name__)

# TD-01（2026-08-18 四方批准·Hermes代改）：intent 重估跳过前缀——集中常量，禁止散落 if
# 覆盖：系统注入 nudge（[BLOCKED/[SEARCH-FIRST/【架构/[intent-action-guard]）
#      + intent-context 注入文本自身（<intent-context> 开头，user 角色）
#      + TD-02 摘要注入（[HISTORY SUMMARY]）
_INTENT_SKIP_PREFIXES = (
    "[BLOCKED", "[SEARCH-FIRST", "【架构", "[intent-action-guard]",
    "[intent-context]", "[HISTORY SUMMARY]", "<intent-context>",
)


# ============== Helpers ==============

def _extract_reasoning(message) -> Optional[str]:
    """Extract reasoning from message - handles dict and object forms."""
    if hasattr(message, "reasoning_content") and message.reasoning_content:
        return message.reasoning_content
    if hasattr(message, "reasoning") and message.reasoning:
        return message.reasoning
    if hasattr(message, "reasoning_details") and message.reasoning_details:
        for detail in message.reasoning_details:
            if hasattr(detail, "text") and detail.text:
                return detail.text
            if isinstance(detail, dict) and detail.get("text"):
                return detail["text"]
    return None


def _tc_to_dict(tc) -> dict:
    """Normalize tool_call to canonical dict (handles object and dict forms)."""
    if isinstance(tc, dict):
        func = tc.get("function", {})
        return {
            "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
            "type": "function",
            "function": {
                "name": func.get("name", tc.get("name", "")),
                "arguments": func.get("arguments", tc.get("arguments", "{}")),
            },
        }
    return {
        "id": tc.id,
        "type": "function",
        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
    }


def _get_tc_name(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("function", {}).get("name", tc.get("name", ""))
    return tc.function.name


def _get_tc_args(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("function", {}).get("arguments", tc.get("arguments", "{}"))
    return tc.function.arguments


def _get_tc_id(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("id", "")
    return tc.id


class AgentLoopExit(Exception):
    """Raised inside the agent loop to exit through the unified validation path.

    Backend Architect 方案 B2（2026-08-15）：7 个结束路径统一 raise 此异常，
    由 run() 外层的 except 捕获，走同一个交付物校验出口——结构性保证
    （未来加第 8 个退出点，只要 raise AgentLoopExit 就自动过校验）。
    """

    def __init__(self, reason: str, result_kwargs: dict):
        super().__init__(reason)
        self.reason = reason
        self.result_kwargs = result_kwargs


# ============== The Loop ==============

class MimirAgentLoop:
    """Pure agent execution engine following the Hermes microkernel pattern.

    Responsibilities:
      - Call the model repeatedly until it stops calling tools
      - Dispatch tool calls to a provided executor
      - Collect errors and metadata in AgentResult
      - Apply budget controls
      - Support interruption

    Does NOT manage: models, credentials, system prompts, tool registration.
    Those belong to the configuration layer (MimirAetherAgent).
    """

    def __init__(
        self,
        model_call: Callable[[List[Dict[str, Any]]], Awaitable[Any]],
        tool_schemas: List[Dict[str, Any]],
        valid_tool_names: Set[str],
        tool_dispatcher: Callable[[str, dict, Optional[str]], str],
        max_turns: int = 90,
        task_id: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        budget_config: Any = None,
        interrupt_check: Optional[Callable[[], bool]] = None,
        compressor: Any = None,  # P0-3: optional in-loop compressor; None = disabled
    ):
        self.model_call = model_call
        self.tool_schemas = tool_schemas
        self.valid_tool_names = valid_tool_names
        self.tool_dispatcher = tool_dispatcher
        self.max_turns = max_turns
        self._read_paths: set = set()  # ADR-008 重复读检测
        self._read_paths_count: dict = {}  # ADR-008 重复计数
        self.task_id = task_id or str(uuid.uuid4())
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = extra_body
        self.budget_config = budget_config
        self.interrupt_check = interrupt_check or (lambda: False)
        # P0-3: in-loop compressor (supplement to core_loop pre-compress)
        self.compressor = compressor
        # Optional execution pipeline (recording + quality tracking)
        self._recorder = None
        # Interval nudge flag: once per session (MW-04)
        self._interval_nudge_done = False
        self._parallel_read_nudge_done = False
        # TD-01（2026-08-18 Hermes代改）：intent 重估的原始输入快照——防自触发循环
        self._last_intent_source: Optional[str] = None
        # TD-03（2026-08-18 Hermes代改）：产出校验硬拦截计数（L2 触发后累计）
        self._production_hard_nudges: int = 0

    async def _loop_body(self, messages: List[Dict[str, Any]]) -> AgentResult:
        """Execute the full agent loop (Loki-C 2026-08-15: run() 改名 _loop_body，薄 run() 在外层 try/except 包装)。

        Args:
            messages: Initial conversation messages (system + user).
                      Modified IN-PLACE.

        Returns:
            AgentResult with full history and metadata.
        """
        reasoning_per_turn: List[Optional[str]] = []
        tool_errors: List[ToolError] = []
        verify_nudges = 0  # verify guard attempts计数（修复：防freeze loop，OpenClaw发现）
        self._task_state = TaskState.PROBING  # task_state注入点1（四方共识：初始探测阶段）
        # B2 (2026-08-19 v2): 任务开始钩子——重置一次性 nudge 标志（防跨任务失效）。
        # core_loop 每次任务新建实例时 __init__ 已重置；此处为实例复用场景的显式保险，
        # 语义从"实例级一次性"升级为"任务级一次性"。
        self.on_task_start()

        user_task = None
        for msg in messages:
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, str) and c.strip():
                    user_task = c.strip()[:500]
                break

        import time as _time
        _executor = get_tool_executor()

        try:
            from agent.execution_pipeline import start_execution_pipeline
            start_execution_pipeline(task_name=user_task or self.task_id, session_id=self.task_id)
        except Exception as exc:
                logger.warning("[%s] _close_pipeline error: %s", self.task_id[:8], exc)

        intent_nudges = 0
        search_first_nudges = 0
        tool_calls_so_far = 0
        _wm_prediction_result = None  # for VoE surprise check

        for turn in range(self.max_turns):
            # ===== 梯度3改造（2026-08-08 四方批准+Hermes代改——装眼睛）=====
            # 产出标记日志：每轮记录"是否有assistant产出"——让"只说不做"在日志里现形
            # 目的：可观测性（刘哥行为观察制度）——Mimir能看见自己的行为→自我改进有依据
            _last_role_before = messages[-1].get("role", "") if messages else ""
            if _last_role_before == "tool":
                logger.info("[%s] turn %d: 上轮以tool结尾——检查本轮是否产出assistant", self.task_id[:8], turn + 1)
            elif _last_role_before == "assistant":
                logger.info("[%s] turn %d: 上轮已有产出（assistant）——正常闭环", self.task_id[:8], turn + 1)
            if self.interrupt_check():
                logger.info("Loop interrupted at turn %d", turn + 1)
                self._close_pipeline(user_task)
                raise AgentLoopExit("interrupt", {
                    "messages": messages, "turns_used": turn + 1,
                    "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                    "tool_errors": tool_errors, "interrupted": True,
                })

            # P1-1 熔断（2026-08-19 执行卡 #5 · OpenClaw cap 修正 + Mimir 细化）：
            # 80 软警告（注入评估提示）——100 硬中断（强制 summary）——env 可关
            _cb_soft = int(os.environ.get("MIMIR_CIRCUIT_SOFT", "80"))
            _cb_hard = int(os.environ.get("MIMIR_CIRCUIT_HARD", "100"))
            if _cb_soft > 0 and turn == _cb_soft - 1:
                _cb_msg = {
                    "role": "user",
                    "content": (
                        "[MIMIR_CIRCUIT_BREAKER] 已运行 80 轮——请评估：当前是在循环/原地打转，"
                        "还是在持续产生新进展？若有进展请简述并继续（预计还需几轮）；"
                        "若在循环请立即收敛：总结已得结论并输出最终答复（不再调用新工具）。"
                    ),
                }
                messages.append(_cb_msg)
                logger.warning("[%s] turn %d: circuit-breaker SOFT warning injected (80 turns)", self.task_id[:8], turn + 1)
            if _cb_hard > 0 and turn >= _cb_hard:
                logger.warning("[%s] turn %d: circuit-breaker HARD cut at %d turns — forcing summary", self.task_id[:8], turn + 1, _cb_hard)
                self._close_pipeline(user_task)
                raise AgentLoopExit("circuit_breaker", {
                    "messages": messages, "turns_used": turn + 1,
                    "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                    "tool_errors": tool_errors, "interrupted": False,
                })

            # 修复（2026-08-05，核心体检-1 P0）：错误风暴检测——工具错误过多=循环卡死信号
            # （原来无上限：工具持续失败会无限continue，浪费token且可能死循环）
            if len(tool_errors) >= 50:
                logger.warning("Tool error storm detected (%d errors) at turn %d — aborting loop", len(tool_errors), turn + 1)
                self._close_pipeline(user_task)
                raise AgentLoopExit("tool_storm", {
                    "messages": messages, "turns_used": turn + 1,
                    "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                    "tool_errors": tool_errors, "interrupted": False,
                })

            turn_start = _time.monotonic()

            mem_nudge = maybe_memory_nudge_message(turn)
            # task_state消费方（四方共识）：WRITING时不注入nudge（不打断写盘）
            if mem_nudge and self._task_state == TaskState.WRITING:
                logger.info("[%s] turn %d: memory nudge skipped (WRITING)", self.task_id[:8], turn + 1)
                mem_nudge = None
            if mem_nudge:
                messages.append({"role": "user", "content": mem_nudge})
                logger.info(
                    "[%s] turn %d: memory nudge (interval=%s)",
                    self.task_id[:8],
                    turn + 1,
                    os.environ.get("MIMIR_MEMORY_NUDGE_INTERVAL", "10"),
                )
            skill_nudge = maybe_skill_nudge_message(turn, tool_calls_so_far)
            # task_state消费方（四方共识）：WRITING时不注入skill nudge（不打断写盘）
            if skill_nudge and self._task_state == TaskState.WRITING:
                logger.info("[%s] turn %d: skill nudge skipped (WRITING)", self.task_id[:8], turn + 1)
                skill_nudge = None
            if skill_nudge:
                messages.append({"role": "user", "content": skill_nudge})

            # Intent predictor context: 每轮重估（TD-01 · 2026-08-18 四方批准 · Hermes代改）
            # 原实现仅 turn 0 注入——长会话用户新输入（追问/换任务）不再重估意图。
            # 修订 1（防自触发循环）：重估对比基于"原始 user 输入快照"（_last_intent_source），
            #   非 messages 尾部——intent-context 注入文本本身是 user 角色，对比尾部会每轮自触发。
            # 修订 2（跳过前缀常量化）：_INTENT_SKIP_PREFIXES 集中管理，禁止散落 if。
            # 逻辑：仅当最新 user 原始文本 != _last_intent_source 且非跳过前缀时重估。
            if intent_predictor_enabled():
                try:
                    _user_text = last_user_text(messages) or ""
                    if (
                        _user_text
                        and _user_text != self._last_intent_source
                        and not _user_text.startswith(_INTENT_SKIP_PREFIXES)
                    ):
                        _pred, _ctx = intent_predict_and_format(_user_text)
                        if _ctx:
                            messages.append({"role": "user", "content": _ctx})
                            self._last_intent_source = _user_text
                            logger.info(
                                "[%s] turn %d: intent-context injected (intent=%s)",
                                self.task_id[:8], turn + 1,
                                _pred.intent if _pred else "none",
                            )
                except Exception as _exc:
                    logger.warning(
                        "[%s] intent predictor skipped: %s",
                        self.task_id[:8], _exc,
                    )

            # P1-1 PI 自动触发（2026-08-19 执行卡 #5 · Loki 修正：轮次预估≥8 才 delegate 非关键词）
            # turn 0 注入一次：任务含"调研/审计/多源验证"且预估轮次≥8 → 提示可 delegate（env MIMIR_PI_FORCE=0 关闭）
            if turn == 0 and os.environ.get("MIMIR_PI_FORCE", "1").strip().lower() not in ("0", "false", "no", "off"):
                try:
                    from agent.pi_trigger import maybe_pi_delegate_nudge
                    _pi_nudge = maybe_pi_delegate_nudge(messages)
                    if _pi_nudge:
                        messages.append({"role": "user", "content": _pi_nudge})
                        logger.info("[%s] turn 1: PI-delegate nudge injected (预估轮次≥8 任务)", self.task_id[:8])
                except Exception as _pie:
                    logger.warning("[%s] PI nudge skipped: %s", self.task_id[:8], _pie)

            # Meta-cognition: scenario → skill_view (turn 0 only, once per user message)
            if turn == 0:
                inject_route, route_skills = should_inject_skill_route_nudge(messages)
                if inject_route:
                    route_msg = build_skill_route_nudge(route_skills)
                    messages.append({"role": "user", "content": route_msg})
                    logger.info(
                        "[%s] turn %d: skill-route nudge → %s",
                        self.task_id[:8],
                        turn + 1,
                        route_skills,
                    )

            # Preemptive session_search: before LLM call, programmatically
            # execute search when cross-session recall is needed.
            # Instead of text-nudging (which the model often ignores), inject
            # actual search results so the model has context to answer from.
            if (
                search_first_guard_enabled()
                and cross_session_requires_search_first(last_user_text(messages))
                and not session_search_satisfied_since_last_user(messages)
            ):
                search_first_nudges += 1
                from tools.session_search_tool import session_search_prefetch
                user_text = last_user_text(messages)
                _q = user_text[:200].strip()
                logger.info(
                    "[%s] turn %d: preemptive session_search for: %s",
                    self.task_id[:8], turn + 1, _q[:80],
                )
                _search_results = []
                try:
                    _r = session_search_prefetch(_q, limit=3, session_limit=2)
                    _search_results = _r if _r else []
                except Exception as _exc:
                    logger.warning("[%s] preemptive search failed: %s", self.task_id[:8], _exc)
                _total = len(_search_results)
                _sessions = len({x.get("session", "") for x in _search_results})
                _nudge = (
                    "[SEARCH-FIRST-RESULTS] Queried sessions."
                    + "\nquery: " + str(_q[:120])
                    + "\nmatches: " + str(_total) + ", sessions: " + str(_sessions)
                    + "\nresults: " + json.dumps(_search_results, ensure_ascii=False)[:2000]
                    + "\nUse these results to answer."
                )
                messages.append({"role": "user", "content": _nudge})

            # WM predictor: advisory context (env MIMIR_WM_PREDICTOR, default off)
            # BUG-19 NOTE (2026-08-03): WM modules archived to
            # docs/archive/world-model-20260803/ — is_wm_predictor_enabled()
            # is always False here (defensive import fallback), so this block
            # is dead code retained for revival reference only.
            if turn == 0 and is_wm_predictor_enabled():
                try:
                    _wm_user = last_user_text(messages)
                    _wm_pred = wm_predict(
                        {
                            "user_message": _wm_user or "",
                            "intent": "",
                            "objective": "",
                        }
                    )
                    if _wm_pred.next_context_needs:
                        _wm_block = (
                            "<wm-prediction>\n"
                            f"  expected_outcome: {_wm_pred.expected_outcome}\n"
                            f"  next_context_needs: {', '.join(_wm_pred.next_context_needs)}\n"
                            f"  applicable_skills: {', '.join(_wm_pred.applicable_skills)}\n"
                            "</wm-prediction>"
                        )
                        _wm_prediction_result = _wm_pred
                        messages.append({"role": "user", "content": _wm_block})
                        logger.info(
                            "[%s] turn %d: wm_prediction needs=%s",
                            self.task_id[:8],
                            turn + 1,
                            _wm_pred.next_context_needs,
                        )
                except Exception as _wm_exc:
                    logger.warning(
                        "[%s] wm_prediction skipped: %s",
                        self.task_id[:8],
                        _wm_exc,
                    )


            # Interval nudge: every N turns (MW-04, env MIMIR_NUDGE_INTERVAL, default 3, 0=off)
            _nudge_interval = int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
            if (
                _nudge_interval > 0
                and turn > 0
                and turn % _nudge_interval == 0
                and not self._interval_nudge_done
            ):
                _interval_nudge = maybe_memory_nudge_message(turn) or maybe_skill_nudge_message(turn, tool_calls_so_far)
                if _interval_nudge:
                    messages.append({"role": "user", "content": _interval_nudge})
                    logger.info(
                        "[%s] turn %d: interval nudge (interval=%d)",
                        self.task_id[:8], turn + 1, _nudge_interval,
                    )
                self._interval_nudge_done = True

            # P0-4: parallel-read nudge (turn>=3, 一次性——防重复注入噪声)
            if not getattr(self, "_parallel_read_nudge_done", False):
                _pr_nudge = maybe_parallel_read_nudge(turn, tool_calls_so_far)
                if _pr_nudge:
                    messages.append({"role": "user", "content": _pr_nudge})
                    logger.info(
                        "[%s] turn %d: parallel-read nudge injected (turn>=3, tools=%d)",
                        self.task_id[:8], turn + 1, tool_calls_so_far,
                    )
                self._parallel_read_nudge_done = True

            # --- In-loop compression (P0-3) ---
            # core_loop pre-compresses once before entering the loop; messages keep
            # growing across turns inside the loop, so re-check before each API call.
            if self.compressor is not None:
                try:
                    if self.compressor.needs_compression(messages):
                        if self.compressor.has_content_to_compress(messages):
                            _pre_n = len(messages)
                            messages, _comp_res = await self.compressor.compress(messages)
                            logger.info(
                                "[%s] turn %d: in-loop compress %d->%d msgs (mode=%s)",
                                self.task_id[:8], turn + 1, _pre_n, len(messages),
                                getattr(_comp_res, "summary_mode", "?"),
                            )
                except Exception as _comp_exc:
                    # compression failure must not break the loop (degrade: keep msgs)
                    logger.warning("[%s] turn %d: in-loop compress failed: %s",
                                   self.task_id[:8], turn + 1, _comp_exc)

            # --- Call model ---
            api_start = _time.monotonic()
            try:
                response = await self.model_call(messages)
            except Exception as e:
                api_elapsed = _time.monotonic() - api_start
                logger.error("API call failed on turn %d (%.1fs): %s", turn + 1, api_elapsed, e)
                self._close_pipeline(user_task)
                raise AgentLoopExit("api_failure", {
                    "messages": messages, "turns_used": turn + 1,
                    "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                    "tool_errors": tool_errors,
                })
            api_elapsed = _time.monotonic() - api_start

            if not response:
                self._close_pipeline(user_task)
                raise AgentLoopExit("empty_response", {
                    "messages": messages, "turns_used": turn + 1,
                    "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                    "tool_errors": tool_errors,
                })

            # --- Extract response parts (dict, MimirAether-flat, or object) ---
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    # Standard OpenAI format: {"choices": [{"message": {...}}]}
                    msg = choices[0].get("message", {})
                    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                    _tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
                    _reasoning = msg.get("reasoning_content") if isinstance(msg, dict) else _extract_reasoning(msg)
                elif "content" in response or "tool_calls" in response:
                    # MimirAether flat format: {"content": ..., "tool_calls": ...}
                    content = response.get("content", "") or ""
                    _tool_calls = response.get("tool_calls")
                    _reasoning = response.get("reasoning_content")
                else:
                    self._close_pipeline(user_task)
                    raise AgentLoopExit("format_error", {
                        "messages": messages, "turns_used": turn + 1,
                        "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                        "tool_errors": tool_errors,
                    })
            else:
                if not getattr(response, "choices", None):
                    self._close_pipeline(user_task)
                    raise AgentLoopExit("no_choices", {
                        "messages": messages, "turns_used": turn + 1,
                        "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                        "tool_errors": tool_errors,
                    })
                msg = response.choices[0].message
                content = getattr(msg, "content", "") or ""
                _tool_calls = getattr(msg, "tool_calls", None)
                _reasoning = _extract_reasoning(msg)

            reasoning_per_turn.append(_reasoning)

            # --- Fallback parser ---
            if not _tool_calls and content and self.tool_schemas and "<tool_call>" in (content or ""):
                _tool_calls = _fallback_parse_tool_calls(content)
                if _tool_calls:
                    tag_idx = content.find("<tool_call>")
                    content = content[:tag_idx].strip()

            # --- Tool calls? ---
            if _tool_calls:
                normalized = [_tc_to_dict(tc) for tc in _tool_calls]
                tool_calls_so_far += len(normalized)
                msg_dict: Dict[str, Any] = {
                    "role": "assistant", "content": content or "",
                    "tool_calls": normalized,
                }
                # DeepSeek 思考模式必须回传 reasoning_content（空串也回传——否则 400）
                msg_dict["reasoning_content"] = _reasoning or ""
                messages.append(msg_dict)

                # Use normalized calls for dispatch so missing `id` matches assistant.tool_calls
                # (dict path in _tc_to_dict synthesizes call_<uuid> when id absent).
                # ---- Parallel dispatch (env MIMIR_PARALLEL_TOOLS=1) ----
                if os.environ.get("MIMIR_PARALLEL_TOOLS", "0") == "1":
                    from .parallel_dispatcher import dispatch_all as _parallel_dispatch_all
                    # Pre-validate: filter unknown tools and bad JSON
                    _valid_norm = []
                    for _tc in normalized:
                        _tname = _get_tc_name(_tc)
                        _targs_raw = _get_tc_args(_tc)
                        _tid = _get_tc_id(_tc)
                        if _tname not in self.valid_tool_names:
                            _tr = json.dumps({"error": f"Unknown tool '{_tname}'."})
                            tool_errors.append(ToolError(
                                turn=turn + 1, tool_name=_tname,
                                arguments=str(_targs_raw)[:200],
                                error=f"Unknown tool '{_tname}'", tool_result=_tr,
                            ))
                            messages.append({"role": "tool", "tool_call_id": _tid, "content": _tr})
                            continue
                        try:
                            json.loads(_targs_raw) if isinstance(_targs_raw, str) else (_targs_raw or {})
                        except json.JSONDecodeError as _e:
                            _tr = json.dumps({"error": f"Invalid JSON: {_e}"})
                            tool_errors.append(ToolError(
                                turn=turn + 1, tool_name=_tname,
                                arguments=str(_targs_raw)[:200],
                                error=f"Invalid JSON: {_e}", tool_result=_tr,
                            ))
                            messages.append({"role": "tool", "tool_call_id": _tid, "content": _tr})
                            continue
                        _valid_norm.append(_tc)
                    if _valid_norm:
                        _batch_results = await _parallel_dispatch_all(
                        _valid_norm, _executor, self.tool_dispatcher, self.task_id,
                    )
                    else:
                        _batch_results = []
                    for _br in _batch_results:
                        if _br is None:
                            continue
                        tname, tid, raw_args, tool_result = _br
                        # task_state注入点2（四方共识）：按工具名更新状态
                        _ts = TaskState.from_tool_name(tname)
                        if _ts is not None:
                            self._task_state = _ts
                        try:
                            t0 = _time.monotonic()
                            from agent.tool_event_emitter import (
                                emit_tool_execution_end,
                                emit_tool_execution_start,
                            )
                            emit_tool_execution_start(
                                tname, {"raw_args": raw_args[:200]}, session_id=self.task_id,
                            )
                            telapsed = _time.monotonic() - t0
                            from agent.tool_outcome import infer_tool_success
                            ok, err_msg = infer_tool_success(str(tool_result))
                            emit_tool_execution_end(
                                tname, success=ok, duration_ms=telapsed * 1000,
                                session_id=self.task_id, error=err_msg,
                            )
                            self._record_tool(
                                tname, {"raw_args": raw_args[:200]}, success=ok,
                                error_message=err_msg, duration_ms=telapsed * 1000,
                                result_summary=str(tool_result)[:200],
                            )
                            # ADR-008 重复读检测（第一阶段·零行为改变·仅日志）——2026-08-18
                            if tname == "read_file":
                                try:
                                    import json as _json
                                    _args = _json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                                    _rpath = str(_args.get("path", "")).strip()
                                    if _rpath:
                                        if _rpath in self._read_paths:
                                            self._read_paths_count[_rpath] = self._read_paths_count.get(_rpath, 1) + 1
                                            import logging as _logging
                                            _logging.getLogger("agent.agent_loop").warning(
                                                f"[dup-read] 重复读取同一文件 {_rpath} 第{self._read_paths_count[_rpath]}次——若已连续多轮无落盘，请停止读取直接产出（ADR-008）")
                                        else:
                                            self._read_paths.add(_rpath)
                                            self._read_paths_count[_rpath] = 1
                                except Exception:
                                    pass
                            if not ok:
                                tool_errors.append(ToolError(
                                    turn=turn + 1, tool_name=tname,
                                    arguments=str(raw_args)[:200],
                                    error=err_msg or "Tool execution failed",
                                    tool_result=str(tool_result)[:500],
                                ))
                        except Exception:
                            pass
                        try:
                            from tools.tool_result_storage import maybe_persist_tool_result
                            from tools.terminal_tool import get_active_env
                            tool_result = maybe_persist_tool_result(
                                content=tool_result, tool_name=tname,
                                tool_use_id=tid,
                                env=get_active_env(self.task_id),
                                config=self.budget_config,
                            )
                        except Exception:
                            pass
                        messages.append({"role": "tool", "tool_call_id": tid, "content": tool_result})
                    tool_calls_so_far += len(normalized)
                else:
                    for tc in normalized:
                        tname = _get_tc_name(tc)
                        targs_raw = _get_tc_args(tc)
                        tid = _get_tc_id(tc)

                        if tname not in self.valid_tool_names:
                            tr = json.dumps({"error": f"Unknown tool '{tname}'."})
                            tool_errors.append(ToolError(
                                turn=turn + 1, tool_name=tname,
                                arguments=str(targs_raw)[:200],
                                error=f"Unknown tool '{tname}'", tool_result=tr,
                            ))
                            messages.append({"role": "tool", "tool_call_id": tid, "content": tr})
                            continue

                        try:
                            args = json.loads(targs_raw) if isinstance(targs_raw, str) else (targs_raw or {})
                        except json.JSONDecodeError as e:
                            tr = json.dumps({"error": f"Invalid JSON: {e}"})
                            tool_errors.append(ToolError(
                                turn=turn + 1, tool_name=tname,
                                arguments=str(targs_raw)[:200],
                                error=f"Invalid JSON: {e}", tool_result=tr,
                            ))
                            messages.append({"role": "tool", "tool_call_id": tid, "content": tr})
                            continue

                        try:
                            t0 = _time.monotonic()
                            _tn, _ta, _tid = tname, args, self.task_id
                            from agent.tool_event_emitter import (
                                emit_tool_execution_end,
                                emit_tool_execution_start,
                            )

                            emit_tool_execution_start(
                                tname, args, session_id=self.task_id
                            )
                            tool_result = await asyncio.get_running_loop().run_in_executor(
                                _executor,
                                lambda tn=_tn, ta=_ta, tid=_tid: self.tool_dispatcher(tn, ta, tid),
                            )
                            telapsed = _time.monotonic() - t0

                            pool_q = _executor._work_queue.qsize()
                            if telapsed > 30:
                                logger.warning(
                                    "[%s] turn %d: %s took %.1fs (pool q=%d)",
                                    self.task_id[:8], turn + 1, tname, telapsed, pool_q,
                                )
                            from agent.tool_outcome import infer_tool_success

                            ok, err_msg = infer_tool_success(str(tool_result))
                            emit_tool_execution_end(
                                tname,
                                success=ok,
                                duration_ms=telapsed * 1000,
                                session_id=self.task_id,
                                error=err_msg,
                            )
                            self._record_tool(
                                tname,
                                args,
                                success=ok,
                                error_message=err_msg,
                                duration_ms=telapsed * 1000,
                                result_summary=str(tool_result)[:200],
                            )
                        except Exception as e:
                            telapsed = _time.monotonic() - t0
                            tool_result = json.dumps({
                                "error": f"{type(e).__name__}: {str(e)}"
                            })
                            tool_errors.append(ToolError(
                                turn=turn + 1, tool_name=tname,
                                arguments=str(targs_raw)[:200],
                                error=f"{type(e).__name__}: {str(e)}",
                                tool_result=tool_result,
                            ))
                            emit_tool_execution_end(
                                tname,
                                success=False,
                                duration_ms=telapsed * 1000,
                                session_id=self.task_id,
                                error=str(e)[:500],
                            )
                            self._record_tool(tname, args, success=False,
                                              error_message=str(e)[:500],
                                              duration_ms=telapsed * 1000,
                                              result_summary=str(tool_result)[:200])

                        # Budget control
                        try:
                            from tools.tool_result_storage import maybe_persist_tool_result
                            from tools.terminal_tool import get_active_env
                            tool_result = maybe_persist_tool_result(
                                content=tool_result, tool_name=tname,
                                tool_use_id=tid,
                                env=get_active_env(self.task_id),
                                config=self.budget_config,
                            )
                        except Exception:
                            pass

                        messages.append({"role": "tool", "tool_call_id": tid, "content": tool_result})
                turn_elapsed = _time.monotonic() - turn_start
                logger.info(
                    "[%s] turn %d: api=%.1fs, %d tools, total=%.1fs",
                    self.task_id[:8], turn + 1, api_elapsed,
                    len(_tool_calls), turn_elapsed,
                )
                # --- VoE surprise check: compare WM prediction vs actual tools ---
                # BUG-02 FIX (2026-08-03): old logic recorded a surprise only
                # when prediction set and actual set had ZERO intersection, and
                # joined the whole predicted set into one "expected" string —
                # producing 84.8% malformed keys that could never be looked up.
                # Now each mismatch is recorded per-tool (expected=missing
                # predicted tool, actual=the tool actually used).
                # NOTE: WM modules are archived (2026-08-03) — this block is
                # inert while is_wm_predictor_enabled() is False.
                if _wm_prediction_result is not None and _tool_calls:
                    _predicted_skills = set(s.lower() for s in (_wm_prediction_result.applicable_skills or []))
                    _actual_tools = set()
                    for _tc_node in (normalized if isinstance(normalized, list) else (_tool_calls or [])):
                        _tname = (_tc_node.get("function", {}).get("name", "") if isinstance(_tc_node, dict) else str(_tc_node)).lower()
                        if _tname:
                            _actual_tools.add(_tname)
                    if _predicted_skills and _actual_tools:
                        _unused_predicted = _predicted_skills - _actual_tools
                        _unpredicted_used = _actual_tools - _predicted_skills
                        if _unused_predicted or _unpredicted_used:
                            try:
                                for _missed in sorted(_unused_predicted):
                                    append_surprise_event(
                                        expected=_missed,
                                        actual=", ".join(sorted(_unpredicted_used)) or "(none)",
                                        surprise_label="wm_prediction_mismatch",
                                        context_snapshot={"turn": turn + 1},
                                        guard_message=f"predicted={_predicted_skills}, actual={_actual_tools}",
                                    )
                            except Exception as exc:
                                logger.warning("[%s] VoE surprise write failed: %s", self.task_id[:8], exc)
            else:
                # No tool calls — finish unless intent-action guard blocks deferral.
                msg_dict = {"role": "assistant", "content": content or ""}
                # DeepSeek 思考模式必须回传 reasoning_content（空串也回传——否则 400）
                msg_dict["reasoning_content"] = _reasoning or ""
                messages.append(msg_dict)

                if (
                    search_first_guard_enabled()
                    and search_first_nudges < MAX_SEARCH_FIRST_NUDGES
                    and should_block_search_first_finish(
                        messages,
                        content or "",
                        has_tool_schemas=bool(self.tool_schemas),
                    )
                ):
                    search_first_nudges += 1
                    # Hard block: auto-execute preemptive search with search results.
                    try:
                        _q = (last_user_text(messages) or "")[:200].strip()
                        _search_results = session_search_prefetch(_q, limit=3, session_limit=2) or []
                        _total = len(_search_results)
                        _sessions = len({x.get("session", "") for x in _search_results})
                        _preemptive = (
                            "[SEARCH-FIRST-RESULTS] Queried sessions."
                            + "\nquery: " + str(_q[:120])
                            + "\nmatches: " + str(_total) + ", sessions: " + str(_sessions)
                            + "\nresults: " + json.dumps(_search_results, ensure_ascii=False)[:2000]
                            + "\nUse these results to answer."
                        )
                        messages.append({"role": "user", "content": _preemptive})
                    except Exception:
                        pass
                    messages.append({"role": "user", "content": build_search_first_nudge()})
                    logger.warning(
                        "[%s] turn %d: search-first guard hard-block %d/%d",
                        self.task_id[:8],
                        turn + 1,
                        search_first_nudges,
                        MAX_SEARCH_FIRST_NUDGES,
                    )
                    continue

                block_finish = (
                    guard_enabled()
                    and intent_nudges < MAX_INTENT_NUDGES
                    and should_block_text_only_finish(
                        messages,
                        content or "",
                        has_tool_schemas=bool(self.tool_schemas),
                    )
                )
                if block_finish:
                    intent_nudges += 1
                    messages.append({"role": "user", "content": build_nudge_message()})
                    logger.warning(
                        "[%s] turn %d: intent-action guard nudge %d/%d (deferred text-only)",
                        self.task_id[:8], turn + 1, intent_nudges, MAX_INTENT_NUDGES,
                    )
                    continue

                # --- verify-before-report guard ---
                if (
                    verify_guard_enabled()
                    and verify_nudges < MAX_VERIFY_NUDGES
                    and should_block_verify_finish(messages, content or "")
                ):
                    # Hard block: remove unverified assistant response from history
                    if messages and messages[-1].get("role") == "assistant":
                        messages.pop()
                    messages.append({"role": "user", "content": build_verify_nudge()})
                    # OC-01: record_retro archived
                    # record_retro(messages, content or "")
                    verify_nudges += 1  # 修复（2026-08-05，OpenClaw发现）：attempts计数——防freeze loop
                    logger.warning(
                        "[%s] turn %d: verify-before-report guard nudge %d/%d",
                        self.task_id[:8], turn + 1, verify_nudges, MAX_VERIFY_NUDGES,
                    )
                    continue

                logger.info(
                    "[%s] turn %d: api=%.1fs, no tools (finished)",
                    self.task_id[:8], turn + 1, api_elapsed,
                )
                # ===== 架构修复2（2026-08-08）+ Loki-C commit 3（2026-08-15）：主动结束路径检查产出 =====
                # 问题：no tools 正常结束路径无产出检查——若最后 assistant 只是"调查总结"无落盘动作→0产出静默
                # 修复：检查本会话是否真的产出过（写盘动作）——若无→注入产出提示（引导补产出）
                _has_written = self._check_has_written(messages)
                # ===== 架构修复（2026-08-18 拆关注点）：产出校验独立于 nudge 开关 =====
                # 问题：nudge 停用（MIMIR_NUDGE_ENABLED=0 治空洞确认）→ _nudge_enabled()=False
                #       → 本 if 短路 → 产出校验失效 → run 无交付也能自然结束
                #       （2026-08-18 实证：872d92cc 12步 / a0b777b 6步 均无写盘结束）
                # 修复：_has_written 校验独立触发——nudge 开关只控制"记忆/技能 nudge"（空洞确认源），
                #       不控制"产出校验"（写盘强制）——两个关注点解耦
                # ===== TD-03（2026-08-18 四方批准·Hermes代改）：产出校验三级强制 =====
                # L1 软提示（现状）→ L2 硬拦截（移除无产出回复+明确指令）→ L3 中断（INTERRUPTED 透传用户）
                # env 门控：MIMIR_PRODUCTION_ENFORCE=1 开启三级；关闭时保持现状（L1 后自然退出）
                if (not _has_written
                        and any(m.get("role") == "assistant" for m in messages)
                        and self._should_nudge_production(messages)):
                    _enforce = os.environ.get("MIMIR_PRODUCTION_ENFORCE", "0").strip().lower() not in ("0", "false", "no")
                    _max_hard = int(os.environ.get("MIMIR_PRODUCTION_HARD_NUDGES", "2") or "2")
                    # TD-03 修订1：research 实质回答豁免（≥50字+实词≥10+无未完成信号+无系统标记 → 视为产出）
                    if self._is_substantive_research_answer(messages):
                        logger.info(
                            "[%s] turn %d: research 实质回答豁免（≥50字+实词≥10）——视为产出，自然退出",
                            self.task_id[:8], turn + 1,
                        )
                    elif _enforce and self._production_hard_nudges >= _max_hard:
                        # L3 中断：连续 _max_hard 次硬拦截后仍无产出 → INTERRUPTED 透传用户
                        logger.warning(
                            "[%s] turn %d: TD-03 L3 中断（has_written=False，硬拦截 %d/%d）——透传用户",
                            self.task_id[:8], turn + 1,
                            self._production_hard_nudges, _max_hard,
                        )
                        self._close_pipeline(user_task)
                        self._task_state = TaskState.INTERRUPTED  # L3 中断状态（四方共识：禁止标 DONE）
                        raise AgentLoopExit("interrupt", {
                            "messages": messages, "turns_used": turn + 1,
                            "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
                            "tool_errors": tool_errors, "interrupted": True,
                        })
                    elif _enforce and self._production_hard_nudges >= 1:
                        # L2 硬拦截：移除最后无产出 assistant 回复 + 注入明确指令（复用 verify guard 移除机制）
                        # R5（OpenClaw）：工具结果已返回则放行——用户应看到结果
                        _tool_result_pending = any(m.get("role") == "tool" for m in messages[-4:])
                        if not _tool_result_pending:
                            while messages and messages[-1].get("role") == "assistant":
                                messages.pop()
                            messages.append({
                                "role": "user",
                                "content": self._build_production_hard_nudge(self._production_hard_nudges, _max_hard),
                            })
                            self._production_hard_nudges += 1
                            logger.warning(
                                "[%s] turn %d: TD-03 L2 硬拦截 %d/%d（移除无产出回复+明确指令）",
                                self.task_id[:8], turn + 1,
                                self._production_hard_nudges, _max_hard,
                            )
                            continue
                        # 工具结果已返回 → 放行（用户应看到结果）
                    elif _enforce:
                        # L1（enforce 开启）：软提示后 continue——给 LLM 下一轮补产出机会（不直接自然退出）
                        logger.info(
                            "[%s] turn %d: TD-03 L1 软提示（enforce 开启）——注入产出提示后继续",
                            self.task_id[:8], turn + 1,
                        )
                        await self._inject_production_nudge(messages)
                        self._production_hard_nudges = 1
                        continue
                    else:
                        # 门控关闭：保持现状 L1 软提示后自然退出
                        logger.info(
                            "[%s] turn %d: 主动结束但无写盘产出——追加产出提示（产出校验独立于nudge开关）", self.task_id[:8], turn + 1
                        )
                        await self._inject_production_nudge(messages)
                self._close_pipeline(user_task)
                self._task_state = TaskState.DONE  # task_state注入点3（四方共识：自然退出→DONE）
                raise AgentLoopExit("natural", {
                    "messages": messages, "turns_used": turn + 1,
                    "finished_naturally": True, "reasoning_per_turn": reasoning_per_turn,
                    "tool_errors": tool_errors,
                })

        # Hit max turns
        logger.info("Agent hit max_turns (%d)", self.max_turns)
        self._close_pipeline(user_task)
        # Nudge-only iterations should not count against budget.
        _nudge_turns = intent_nudges + search_first_nudges
        _effective_turns = max(1, self.max_turns - _nudge_turns)
        # ===== 架构修复（2026-08-08 刘哥洞察+四方共识）：耗尽→强制产出 =====
        # 问题：max_turns耗尽直接返回——若最后是工具调用（无assistant回复）→0产出静默结束
        # 修复：检查messages最后一条——若是tool角色（工具结果）→追加强制总结请求（一次额外LLM调用）
        _last_role = messages[-1].get("role", "") if messages else ""
        if _last_role == "tool":
            logger.info("[%s] max_turns reached with pending tool result — forcing final summary", self.task_id[:8])
            try:
                _force_msg = {
                    "role": "user",
                    "content": (
                        "【架构强制产出】你已用完迭代预算但最后一步是工具调用，尚未给出最终答复。\n"
                        "现在请立即输出你的最终答复：\n"
                        "1. 总结你已完成的分析/调研（如有落盘要求，用 write_file/patch 写入指定路径）\n"
                        "2. 输出最终结论（直接可用，50-200字）\n"
                        "3. 不要调用新工具（除了必需的写盘）——直接回答"
                    ),
                }
                messages.append(_force_msg)
                try:
                    _resp = await self.model_call(messages)
                    if _resp is not None:
                        _text = getattr(_resp, "content", None) or (getattr(_resp, "message", None) or {}).get("content") if not hasattr(_resp, "content") else getattr(_resp, "content", None)
                        if _text:
                            messages.append({"role": "assistant", "content": _text})
                            logger.info("[%s] forced summary appended (%d chars)", self.task_id[:8], len(str(_text)))
                except Exception as _exc2:
                    logger.warning("[%s] forced summary model_call failed: %s", self.task_id[:8], _exc2)
            except Exception as _exc:
                logger.warning("[%s] forced summary failed: %s", self.task_id[:8], _exc)
        raise AgentLoopExit("max_turns", {
            "messages": messages, "turns_used": _effective_turns,
            "finished_naturally": False, "reasoning_per_turn": reasoning_per_turn,
            "tool_errors": tool_errors,
        })

    async def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        """薄 run 包装器（Loki-C 2026-08-15）：try/except 捕获 AgentLoopExit，统一出口。

        保留 run 作为 public API——子类 MimirAetherAgentLoop.run（L1070 附近）
        仍调用 self._loop.run(...)，此处补齐 run 后不断链。
        """
        try:
            return await self._loop_body(messages)
        except AgentLoopExit as _exit:
            return await self._finalize_exit(_exit.reason, _exit.result_kwargs)

    def on_task_start(self) -> None:
        """B2 (2026-08-19 v2): 任务开始钩子——重置一次性 nudge 标志（防跨任务失效）。

        _parallel_read_nudge_done 语义为"每个任务最多注入一次并行读 nudge"。
        __init__ 仅在实例创建时重置；若同一实例被复用执行多个任务
        （如会话级长驻 loop / benchmark 循环复用），第二个任务将因 flag 残留
        而不再收到 nudge。本钩子在 _loop_body（每次 run 即每个任务）开头调用。
        """
        self._parallel_read_nudge_done = False

    def _check_has_written(self, messages: List[Dict[str, Any]]) -> bool:
        """检查会话是否产生过写盘产出（Loki-C commit 3 提取 + 2026-08-16 目标校验升级）。

        复用修复 A（2026-08-15）：按 assistant tool_calls 的 function.name 精确判断，
        弃用 content 字符串匹配（"bytes" 太宽泛，read_file 读大文件返回 "large bytes" 误判已写盘）。

        2026-08-16 升级（治"写了工作记忆≠写了交付物"）：提取 write_file/patch 的目标路径，
        排除工作记忆（search-notes.md 等），只有写到真实交付物才算"有产出"。
        根因：Mimir 写 search-notes.md（工作记忆）后 _check_has_written=True 放过，
        但目标交付物（讨论卡段）没写——"写到别处不算"。
        """
        import re as _re
        _WRITE_TOOLS = {"write_file", "patch", "create_file", "edit", "write"}
        _WORK_MEMORY_KEYS = ("search-notes.md", "/tmp/", "PROGRESS.md")
        for m in messages:
            if m.get("role") != "assistant":
                continue
            for tc in (m.get("tool_calls") or []):
                if _get_tc_name(tc) not in _WRITE_TOOLS:
                    continue
                args_raw = _get_tc_args(tc)
                args_str = args_raw if isinstance(args_raw, str) else json.dumps(args_raw, ensure_ascii=False)
                # 提取目标路径（write_file 的 path / patch 的 path / file_path 等）
                _paths = _re.findall(
                    r'["\']?([\w./~-]+\.(?:md|py|json|txt|yaml|yml|sh|log))["\']?',
                    args_str,
                )
                # 只要有一个非工作记忆的交付物路径，就算有产出
                if any(p and not any(k in p for k in _WORK_MEMORY_KEYS) for p in _paths):
                    return True
        return False

    def _nudge_enabled(self) -> bool:
        """nudge 机制总开关（2026-08-17 刘哥拍板停用）：MIMIR_NUDGE_ENABLED=0 → 停用，靠提示词主动落盘。"""
        return os.environ.get("MIMIR_NUDGE_ENABLED", "1").strip().lower() not in ("0", "false", "no")

    # 系统注入消息前缀（guard 提示/软提示/intent 上下文/skill nudge）——非真实用户指令
    _SYSTEM_INJECT_PREFIXES = (
        "[MIMIR_", "[BLOCKED:", "[SEARCH-FIRST", "<intent-context>",
        "【架构产出提示】", "[intent-action-guard]",
    )

    def _should_nudge_production(self, messages: List[Dict[str, Any]]) -> bool:
        """问答型豁免（2026-08-17 刘哥根治）：最后一条真实 user 消息是简短问答/催促（无任务词）→ 不触发产出提示。
        根因：刘哥问"怎么不回答了？"被 nudge 劫持成"收到——落盘"模板，答非所问。"""
        # TD-03 修订5（2026-08-18 Mimir 审计 P0-1）：intent=chat 豁免——意图分类器已判纯对话，
        # 不强制写盘产出（对齐 OpenClaw R4 预警"长回复正常收尾误伤" + 5 回归根因：纯文本 chat 被 L2/L3 硬拦）。
        # 修订6（同轮）：跳过全部系统注入消息（intent-context/skill nudge/软提示/guard 提示）——
        # 只看最后一条真实用户消息，与 verify guard 的 _is_system_inject 对齐（防"软提示含落盘字样"误判链）。
        for m in reversed(messages):
            if m.get("role") == "user":
                _c = m.get("content", "")
                if not isinstance(_c, str):
                    continue
                if "intent=chat" in _c:
                    return False  # 纯对话 → 豁免产出强制，自然退出即可
                if _c.startswith(self._SYSTEM_INJECT_PREFIXES):
                    continue  # 系统注入消息 → 跳过，继续找真实 user 消息
                break
        _task_words = ("落盘", "记录", "报告", "分析", "审计", "整理", "写", "总结",
                       "查找", "找", "搜索", "任务", "生成", "创建", "修复", "执行",
                       "论文", "调研", "查", "评估", "检查", "对比")
        for m in reversed(messages):
            if m.get("role") == "user":
                _t = m.get("content", "")
                if isinstance(_t, list):
                    _t = " ".join(str(x.get("text", "")) for x in _t if isinstance(x, dict))
                _t = str(_t).strip()
                if _t.startswith(self._SYSTEM_INJECT_PREFIXES):
                    continue  # 同上：系统注入消息不参与问答型豁免判断
                _is_question = _t.endswith(("？", "?", "吗", "呢", "了", "？"))
                if (len(_t) < 40 and not any(w in _t for w in _task_words)) or (_is_question and len(_t) < 60):
                    return False  # 简短催促/追问/问答 → 豁免，直接回答即可
                break
        return True

    # ===== TD-03（2026-08-18 四方批准·Hermes代改）：research 实质回答豁免 + L2 硬拦截指令 =====
    _UNFINISHED_SIGNALS = ("准备", "接下来", "将要", "即将")
    _SYS_MARKS = ("[WAIT]", "[TODO]", "[BLOCKED]")
    _STOP_WORDS = {"一个", "我们", "你们", "他们", "这个", "那个", "可以", "需要",
                   "进行", "以及", "对于", "因为", "所以", "但是", "然后", "就是", "已经"}

    def _is_substantive_research_answer(self, messages: List[Dict[str, Any]]) -> bool:
        """TD-03 修订1（OpenClaw R4）：research 实质回答豁免——≥50字 + 实词≥10 + 无未完成信号 + 无系统标记 → 视为产出。

        误伤场景防住：综述型 research 回答本身即产出（不要求写盘）。
        """
        import re as _re
        # 取最后一条 assistant 文本
        _text = ""
        for m in reversed(messages):
            if m.get("role") == "assistant" and m.get("content"):
                _c = m["content"]
                _text = _c if isinstance(_c, str) else str(_c)
                break
        if len(_text) < 50:
            return False
        if any(w in _text for w in self._UNFINISHED_SIGNALS):
            return False
        if any(mk in _text for mk in self._SYS_MARKS):
            return False
        # 实词统计：中文字词 + 英文单词（粗粒度过滤停用词）
        _words = _re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", _text)
        _content_words = [w for w in _words if w not in self._STOP_WORDS]
        return len(_content_words) >= 10

    def _build_production_hard_nudge(self, attempt: int, max_hard: int) -> str:
        """TD-03 修订4（OpenClaw R7）：L2 硬拦截明确指令——告诉 LLM 已移除 1 次未落盘回复。"""
        return (
            f"[BLOCKED:production-enforce] 你的上一条回复已被移除——本会话仍无写盘产出"
            f"（write_file/patch），且已软提示过 1 次。这是第 {attempt + 1}/{max_hard} 次硬拦截。\n"
            "请立即执行以下之一：\n"
            "1. 如果任务要求落盘：现在就用 write_file/patch 写入交付物（先写盘再总结）\n"
            "2. 如果已完成调研但未落盘：把结论落盘到指定路径，再输出简短总结\n"
            "3. 如果用户只是问答/闲聊：直接给出完整回答（≥50字实质内容即可）\n"
            "不要输出'收到——落盘'式空洞确认。"
        )

    async def _inject_production_nudge(self, messages: List[Dict[str, Any]]) -> None:
        """注入产出提示（架构修复2 + Loki-C commit 3 提取）：无写盘产出时引导落盘（best-effort，不抛）。"""
        try:
            _prod_msg = {
                "role": "user",
                "content": (
                    "【架构产出提示】你即将结束任务，但本会话尚未产生任何写盘产出（write_file/patch）。\n"
                    "如果任务要求产出（分析结论/审计报告/记录），请立即用 write_file/patch 落盘到指定路径——"
                    "否则任务视为未完成。\n"
                    "如果用户只是问答/闲聊/催促（不需要落盘产出），直接回答用户问题即可——回答本身就是完成。"
                ),
            }
            messages.append(_prod_msg)
            _resp = await self.model_call(messages)
            if _resp is not None:
                _msg = None
                _choices = getattr(_resp, "choices", None)
                if isinstance(_choices, list) and _choices:
                    _c0 = _choices[0]
                    _msg = _c0.get("message") if isinstance(_c0, dict) else getattr(_c0, "message", None)
                if _msg is None and (hasattr(_resp, "content") or isinstance(_resp, dict)):
                    _msg = _resp
                _text = None
                _tool_calls = None
                if isinstance(_msg, dict):
                    _text = _msg.get("content")
                    _tool_calls = _msg.get("tool_calls")
                elif _msg is not None:
                    _text = getattr(_msg, "content", None)
                    _tool_calls = getattr(_msg, "tool_calls", None)
                # 2026-08-16 修复（Code Reviewer）：产出提示后的写盘 tool_call 必须执行，否则"提醒了但动作被丢弃"
                # 根因：旧实现只提取 content 文本，丢弃 tool_calls——Mimir 响应产出提示想 write_file 时动作被丢，仍 0 落盘
                if _tool_calls:
                    _executor = get_tool_executor()
                    for _tc in _tool_calls:
                        _tname = _get_tc_name(_tc)
                        if _tname not in {"write_file", "patch", "create_file", "edit", "write"}:
                            continue
                        _targs_raw = _get_tc_args(_tc)
                        _tid = _get_tc_id(_tc)
                        try:
                            _ta = json.loads(_targs_raw) if isinstance(_targs_raw, str) else (_targs_raw or {})
                        except Exception:
                            _ta = {}
                        try:
                            _result = await asyncio.get_running_loop().run_in_executor(
                                _executor,
                                lambda tn=_tname, ta=_ta, tid=_tid: self.tool_dispatcher(tn, ta, tid),
                            )
                            messages.append({"role": "tool", "tool_call_id": _tid, "content": str(_result)})
                            logger.info("[%s] 产出提示后写盘执行: %s", self.task_id[:8], _tname)
                        except Exception as _te:
                            logger.warning("[%s] 产出提示后写盘失败: %s", self.task_id[:8], _te)
                if _text:
                    messages.append({"role": "assistant", "content": _text})
        except Exception as _pexc:
            logger.warning("[%s] 产出提示失败: %s", self.task_id[:8], _pexc)

    async def _finalize_exit(self, reason: str, result_kwargs: dict) -> AgentResult:
        """统一出口（Loki-C）：所有退出路径汇聚于此。

        commit 3（spec 完整落地）：_has_written 校验 + [EXIT] 四要素日志 +
        异常路径注入产出提示（治"探索完就停"核心）+ try/except 兜底。
        """
        try:
            messages = result_kwargs.get("messages") or []
            # 主动停止（用户中断/系统错误风暴）不视为漏产出
            _ACTIVE_STOP_REASONS = {"interrupt", "tool_storm"}
            _has_written = self._check_has_written(messages)
            # SRE 三件套之二：exit 四要素日志（reason/has_written/task/turns）
            logger.info("[%s] [EXIT] reason=%s turns=%s has_written=%s active_stop=%s",
                        self.task_id[:8], reason, result_kwargs.get("turns_used"),
                        _has_written, reason in _ACTIVE_STOP_REASONS)
            # 异常路径（api_failure/empty_response/format_error/no_choices）无写盘 → 注入产出提示
            # （natural 循环内已做、max_turns 循环外已做强制产出、interrupt/tool_storm 主动停止）
            if (not _has_written
                    and reason in {"api_failure", "empty_response", "format_error", "no_choices"}
                    and any(m.get("role") == "assistant" for m in messages)):
                logger.info("[%s] [EXIT] 异常路径无写盘产出——注入产出提示", self.task_id[:8])
                await self._inject_production_nudge(messages)
            return AgentResult(**result_kwargs)
        except Exception as _exc:
            # 兜底：_finalize_exit 自身异常不崩 gateway，降级为带错误日志的 AgentResult
            logger.error("[%s] [EXIT] _finalize_exit 兜底: %s", self.task_id[:8], _exc)
            return AgentResult(**result_kwargs)

    def _close_pipeline(self, task_name: str = "") -> None:
        """Defensive close of execution pipeline (best-effort, never raises)."""
        try:
            from agent.execution_pipeline import (
                close_execution_pipeline
            )
            from agent.skill_curator import schedule_skill_curator_lifecycle_pass

            task = task_name or self.task_id
            result = close_execution_pipeline(
                task_name=task,
                session_id=self.task_id,
            )
            schedule_skill_curator_lifecycle_pass(
                session_id=self.task_id,
                task_name=task,
            )
        except Exception as exc:
            logger.warning("[%s] _close_pipeline error: %s", self.task_id[:8], exc)
    def _record_tool(
        self,
        tool_name: str,
        arguments: dict,
        *,
        success: bool,
        error_message: str = "",
        duration_ms: float = 0.0,
        result_summary: str = "",
    ) -> None:
        """Record tool execution to the active pipeline (if any).

        No-op when execution recording is not active.  Always succeeds —
        a recording failure must never break the agent loop.
        """
        try:
            from agent.execution_pipeline import record_tool_call
            record_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
                result_summary=result_summary,
                session_id=self.task_id,
            )
        except Exception as exc:
                logger.warning("[%s] _close_pipeline error: %s", self.task_id[:8], exc)  # Recording is best-effort


def _fallback_parse_tool_calls(content: str) -> Optional[List[dict]]:
    """Parse <tool_call> tags from content when structured tool_calls absent."""
    import re as _re
    pattern = _re.compile(
        r"<tool_call>\s*(.*?)\s*</tool_call>|<tool_call>\s*(.*)",
        _re.DOTALL,
    )
    matches = pattern.findall(content)
    if not matches:
        return None
    parsed = []
    for m in matches:
        raw = m[0] or m[1]
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
            if "name" in data:
                parsed.append({
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": data["name"],
                        "arguments": json.dumps(
                            data.get("arguments", {}), ensure_ascii=False
                        ),
                    },
                })
        except Exception as exc:
                logger.warning("[%s] _close_pipeline error: %s", self.task_id[:8], exc)
    return parsed or None


STRING_PARAM = {"type": "string"}


def tool_schema(name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible helper to build OpenAI function tool schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


class MimirAetherAgentLoop:
    """Compatibility facade for legacy tests/code expecting old constructor."""

    def __init__(
        self,
        chat_fn: Callable[[List[Dict[str, Any]]], Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_turns: int = 90,
        task_id: Optional[str] = None,
    ):
        self._chat_fn = chat_fn
        self._handlers: Dict[str, Callable[[str, dict, Optional[str]], Any]] = {}
        self._tool_schemas = tools or []
        valid_names = {
            t.get("function", {}).get("name")
            for t in self._tool_schemas
            if isinstance(t, dict)
        }
        valid_names = {n for n in valid_names if n}

        async def _model_call(messages: List[Dict[str, Any]]) -> Any:
            out = self._chat_fn(messages)
            if asyncio.iscoroutine(out):
                return await out
            return out

        def _dispatch(name: str, args: dict, session_id: Optional[str]) -> str:
            handler = self._handlers.get(name)
            if handler is None:
                raise NotImplementedError(f"Tool handler not implemented: '{name}'")
            result = handler(name, args, session_id)
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

        self._loop = MimirAgentLoop(
            model_call=_model_call,
            tool_schemas=self._tool_schemas,
            valid_tool_names=valid_names,
            tool_dispatcher=_dispatch,
            max_turns=max_turns,
            task_id=task_id,
        )
        self.valid_tool_names = self._loop.valid_tool_names

    def register_tool(self, name: str, handler: Callable[[str, dict, Optional[str]], Any]) -> None:
        self._handlers[name] = handler

    def register_tools(self, handlers: Dict[str, Callable[[str, dict, Optional[str]], Any]]) -> None:
        for name, handler in handlers.items():
            self.register_tool(name, handler)

    async def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        return await self._loop.run(messages)


class SimpleAgentLoop(MimirAetherAgentLoop):
    """Synchronous wrapper around MimirAetherAgentLoop."""

    def __init__(
        self,
        chat_fn: Callable[[List[Dict[str, Any]]], Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_turns: int = 90,
        task_id: Optional[str] = None,
    ):
        super().__init__(chat_fn=chat_fn, tools=tools, max_turns=max_turns, task_id=task_id)

    def tool(self, name: str) -> Callable[[Callable[[dict], Any]], Callable[[dict], Any]]:
        def _decorator(fn: Callable[[dict], Any]) -> Callable[[dict], Any]:
            def _adapter(_tool_name: str, args: dict, _session_id: Optional[str]) -> Any:
                return fn(args)
            self.register_tool(name, _adapter)
            return fn
        return _decorator

    def run(self, messages: List[Dict[str, Any]]) -> AgentResult:
        return asyncio.run(super().run(messages))
