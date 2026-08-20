"""
ExecMixin — Tool execution: dedup, repair, execute tools.

Extracted from MimirAetherAgent (agent/core_loop.py) as part of d4 split.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import time

from agent.async_bridge import get_tool_executor
from agent.types import ToolError, ToolResult, _get_tool_arguments, _get_tool_id, _get_tool_name
import tools.registry as _tool_registry_module

_tool_executor = get_tool_executor()

from typing import List, Dict, Optional, Any, TYPE_CHECKING
import threading
import queue as _queue
import re

# P3 审计修复（2026-08-18）：审计日志异步写入——磁盘慢/满不阻塞工具调用
_AUDIT_QUEUE = _queue.Queue(maxsize=2000)
_AUDIT_LOGGER_STARTED = False


def _audit_writer_worker() -> None:
    """后台审计写入线程：队列取一条写一条——磁盘慢不影响主流程。"""
    _audit_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", ".mimiraether", "data", "audit",
    )
    _audit_dir = os.path.abspath(_audit_dir)
    try:
        os.makedirs(_audit_dir, exist_ok=True)
    except Exception:
        _audit_dir = "/tmp/mimiraether-audit"  # 兜底
    _log_path = os.path.join(_audit_dir, "external_traffic.log")
    while True:
        try:
            _line = _AUDIT_QUEUE.get(timeout=60)
            if _line is None:
                break
            with open(_log_path, "a", encoding="utf-8") as _af:
                _af.write(_line)
        except _queue.Empty:
            continue
        except Exception:
            pass


def _start_audit_writer() -> None:
    global _AUDIT_LOGGER_STARTED
    if _AUDIT_LOGGER_STARTED:
        return
    _AUDIT_LOGGER_STARTED = True
    threading.Thread(target=_audit_writer_worker, daemon=True).start()




if TYPE_CHECKING:
    from agent.core_loop import MimirAetherAgent

import logging
logger = logging.getLogger(__name__)

# === Module-level helper classes (extracted from core_loop.py) ===

class ToolRegistry:
    """
    ⚠️ DEPRECATED: 工具注册表兼容层。
    委托到 tools.registry.registry，仅保留用于向后兼容。
    新代码应直接使用 tools.registry.registry。
    """

    def __init__(self):
        # 委托到真正的全局 registry（单例）
        self._real_registry = _tool_registry_module.registry

    def register(self, name: str, func: callable, schema: dict):
        """注册工具（委托到真正的 registry）"""
        self._real_registry.register(
            name=name,
            toolset="compat",
            schema={"name": name, "description": schema.get("description", f"Tool: {name}"),
                    "parameters": schema.get("parameters", {})},
            handler=lambda args, **kw: func(**args) if callable(func) else func(args),
        )

    async def execute(self, name: str, arguments: dict):
        """执行工具（委托到真正的 registry.dispatch）"""
        from tools.strategy import route_tool_call

        name, arguments, err = route_tool_call(name, arguments)
        if err:
            return json.dumps({"error": err, "type": "routing_error"})
        result_str = self._real_registry.dispatch(name, arguments)
        return result_str

    def list_tools(self):
        """列出所有工具"""
        return self._real_registry.get_all_tool_names()

    def get_schema(self, name: str):
        """获取工具 schema"""
        return self._real_registry.get_schema(name)




class _BuiltinToolBackend:
    """Default tool path: semaphore + timeouts + registry dispatch (see ``_builtin_execute_tools``)."""

    __slots__ = ("_agent",)

    def __init__(self, agent: "MimirAetherAgent") -> None:
        self._agent = agent

    async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0) -> List[ToolResult]:
        return await self._agent._builtin_execute_tools(tool_calls, turn)




class ExecMixin:
    """Tool execution: dedup, repair, execute tools.

    Designed to be mixed into MimirAetherAgent.
    """
    def _deduplicate_tool_calls(self, tool_calls: list) -> list:
        """
        去除重复的工具调用

        学习自Hermes _deduplicate_tool_calls:
        - 基于(tool_name, arguments)唯一性去重
        - 只保留第一个出现的重复调用
        """
        seen = set()
        unique = []
        for tc in tool_calls:
            # 使用统一工具函数提取名称和参数，兼容OpenAI嵌套格式和旧格式
            name = _get_tool_name(tc)
            arguments = _get_tool_arguments(tc)
            key = (name, arguments if isinstance(arguments, str) else json.dumps(arguments, sort_keys=True))
            if key not in seen:
                seen.add(key)
                unique.append(tc)
            else:
                logger.warning(f"Removed duplicate tool call: {name}")
        return unique if len(unique) < len(tool_calls) else tool_calls

    def _repair_tool_call(self, tool_name: str) -> str | None:
        """
        修复错误的工具名称

        学习自Hermes _repair_tool_call:
        1. 尝试小写
        2. 尝试标准化(下划线替代连字符/空格)
        3. 尝试模糊匹配
        """
        valid_names = set(_tool_registry_module.registry.get_all_tool_names())
        if not valid_names:
            return None

        # 1. 小写匹配
        lowered = tool_name.lower()
        if lowered in valid_names:
            return lowered

        # 2. 标准化匹配
        normalized = lowered.replace('-', '_').replace(' ', '_')
        if normalized in valid_names:
            return normalized

        # 3. 模糊匹配
        import difflib
        matches = difflib.get_close_matches(lowered, valid_names, n=1, cutoff=0.7)
        if matches:
            return matches[0]

        return None

    async def _execute_tools(self, tool_calls: List[Dict], turn: int = 0) -> List[ToolResult]:
        """委托给当前 ``tool_backend``（默认 :class:`_BuiltinToolBackend`）。"""
        return await self._tool_backend.execute_tools(tool_calls, turn)

    async def _builtin_execute_tools(self, tool_calls: List[Dict], turn: int = 0) -> List[ToolResult]:
        """
        内置工具批处理：并发限制、单工具超时、registry 分发。

        学习自Hermes _execute_tools：
        - 收集ToolError实例用于元数据
        - 支持turn参数用于错误追踪
        
        Args:
            tool_calls: 工具调用列表
            turn: 当前轮次(用于错误记录)
        """
        # Tool progress: notify user tools are running
        _tool_labels = []
        for tc in tool_calls:
            fn_name = _get_tool_name(tc) or "unknown"
            _tool_labels.append(fn_name)
        _progress_msg = f"🔧 执行工具: {', '.join(_tool_labels[:4])}{'...' if len(_tool_labels) > 4 else ''}"
        if _tool_labels:
            self._fire_stream_delta(_progress_msg + "\n")

        # 检查是否被中断
        if self._interrupt_requested:
            logger.info("Tool execution skipped: interrupt requested — returning error placeholders for %d tool(s)", len(tool_calls))
            # 关键修复：中断时不能返回空列表！必须给每个 tool_call 补一个错误结果，
            # 否则 conversation_history 中 assistant(tool_calls) 后面缺 tool result，
            # 导致下次 API 调用时 DeepSeek 400: "tool must be a response to tool_calls"
            return [
                ToolResult(
                    tool_call_id=_get_tool_id(tc) or "unknown",
                    content="Tool execution skipped: agent was interrupted",
                    is_error=True
                )
                for tc in tool_calls
            ]

        from agent.search_first_guard import block_tool_reason

        prebuilt: Dict[int, ToolResult] = {}
        to_run: List[tuple[int, Dict]] = []
        for idx, tool_call in enumerate(tool_calls):
            tool_name = _get_tool_name(tool_call) or ""
            block_msg = block_tool_reason(tool_name, self.conversation_history)
            if block_msg:
                tid = _get_tool_id(tool_call) or "unknown"
                prebuilt[idx] = ToolResult(
                    tool_call_id=tid,
                    content=f"Error: {block_msg}",
                    is_error=True,
                )
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=tool_name or "unknown",
                    arguments=str(_get_tool_arguments(tool_call))[:200],
                    error=block_msg,
                    tool_result=f"Error: {block_msg}",
                ))
                logger.warning(
                    "search-first guard blocked tool=%s turn=%s",
                    tool_name,
                    turn,
                )
            else:
                to_run.append((idx, tool_call))

        results = []

        async def execute_with_semaphore(tool_call: Dict) -> ToolResult:
            async with self._tool_semaphore:
                try:
                    return await asyncio.wait_for(
                        self._execute_single_tool(tool_call, turn),
                        timeout=30.0  # 单工具30秒超时
                    )
                except asyncio.TimeoutError:
                    tool_name = _get_tool_name(tool_call) or 'unknown'
                    logger.warning(f"Tool execution timed out: {tool_name}")
                    # Hermes风格:收集ToolError
                    self._tool_errors.append(ToolError(
                        turn=turn,
                        tool_name=tool_name,
                        arguments=str(_get_tool_arguments(tool_call))[:200],
                        error="TimeoutError",
                        tool_result="Error: tool execution timed out",
                    ))
                    return ToolResult(
                        tool_call_id=_get_tool_id(tool_call) or "unknown",
                        content="Error: tool execution timed out",
                        is_error=True
                    )
                except (ValueError, TypeError, KeyError) as e:
                    tool_name = _get_tool_name(tool_call) or 'unknown'
                    logger.warning(f"Tool execution parameter error: {tool_name}: {e}")
                    # Hermes风格:收集ToolError
                    self._tool_errors.append(ToolError(
                        turn=turn,
                        tool_name=tool_name,
                        arguments=str(_get_tool_arguments(tool_call))[:200],
                        error=f"{type(e).__name__}: {e}",
                        tool_result=f"Error: {type(e).__name__} - {e}",
                    ))
                    return ToolResult(
                        tool_call_id=_get_tool_id(tool_call) or "unknown",
                        content=f"Error: {type(e).__name__} - {e}",
                        is_error=True
                    )
                except Exception as e:
                    tool_name = _get_tool_name(tool_call) or 'unknown'
                    logger.error(f"Tool execution error: {tool_name}: {e}")
                    # Hermes风格:收集ToolError
                    self._tool_errors.append(ToolError(
                        turn=turn,
                        tool_name=tool_name,
                        arguments=str(_get_tool_arguments(tool_call))[:200],
                        error=f"{type(e).__name__}: {e}",
                        tool_result=f"Error: {type(e).__name__} - {e}",
                    ))
                    return ToolResult(
                        tool_call_id=_get_tool_id(tool_call) or "unknown",
                        content=f"Error: {type(e).__name__} - {e}",
                        is_error=True
                    )

        # 并发执行允许的工具(受 semaphore 限制)
        run_results: Dict[int, Any] = {}
        if to_run:
            tasks = [execute_with_semaphore(tc) for _, tc in to_run]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, tool_call), result in zip(to_run, gathered):
                run_results[idx] = (tool_call, result)

        # 处理结果（保持与 tool_calls 顺序一致）
        processed_results = []
        for i in range(len(tool_calls)):
            if i in prebuilt:
                processed_results.append(prebuilt[i])
                continue
            tool_call, result = run_results[i]
            if isinstance(result, Exception):
                err_name = type(result).__name__
                err_msg = str(result)
                tool_name = _get_tool_name(tool_call) or 'unknown'
                
                # 记录详细日志但不暴露给LLM
                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(f"Tool execution timed out: {tool_name}")
                    content = "Error: tool execution timed out"
                else:
                    logger.warning(f"Tool execution exception ({err_name}): {tool_name}")
                    content = "Error: tool execution failed"
                
                # Hermes风格:收集ToolError
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=tool_name,
                    arguments=str(_get_tool_arguments(tool_call))[:200],
                    error=f"{err_name}: {err_msg}",
                    tool_result=content,
                ))
                
                processed_results.append(ToolResult(
                    tool_call_id=_get_tool_id(tool_call) or "unknown",
                    content=content,
                    is_error=True
                ))
            else:
                processed_results.append(result)

        # Tool completion summary
        _ok_count = sum(1 for r in processed_results if not r.is_error)
        _err_count = sum(1 for r in processed_results if r.is_error)
        if _err_count > 0:
            self._fire_stream_delta(f"⚠️ {_ok_count}成功 {_err_count}失败\n")
        elif _ok_count > 0:
            self._fire_stream_delta(f"✅ 已完成 ({_ok_count}个工具)\n")

        return processed_results

    # ── 架构硬规则 #5 第 1 层：外部内容校验（2026-08-18 Hermes 执行 · OpenClaw security 方案）──
    # 外部工具（web/网络/抓取）返回内容统一收口校验：大小限制 + 来源标注 + 格式校验 + 敏感词扫描。
    # env 门控 MIMIR_EXTERNAL_VALIDATION（默认 on；off 降级仅保留 1MB 大小保护——
    # 注入/敏感词扫描关闭（E1/E3 文档化：off 是"降级"非"全关"——DENY 类安全底线不随 off 解除）
    _EXTERNAL_TOOLS = (
        "web_search", "web_extract", "web_fetch", "fetch_url", "http_request",
        "curl", "browser_navigate", "browser_snapshot", "browser_console",
    )
    _INJECTION_PATTERNS = (
        "ignore previous instructions", "ignore all previous", "system prompt",
        "you are now", "you are an", "bypass", "disregard", "执行以下指令",
        "忽略之前", "你现在是", "系统提示词", "注入", "攻击",
    )
    _SENSITIVE_PATTERNS = (
        "script>", "shellcode", "exec(", "eval(", "base64 -d", "/etc/passwd",
        "rm -rf /", "chmod 777",
    )

    def _validate_external_content(self, func_name: str, content: str) -> str:
        """外部内容校验（#5 第 1 层）——返回校验后（可能被标记/截断）的内容。"""
        if func_name not in self._EXTERNAL_TOOLS:
            return content
        try:
            _enabled = os.environ.get("MIMIR_EXTERNAL_VALIDATION", "1").strip().lower()
            _on = _enabled not in ("0", "false", "no", "off")
        except Exception:
            _on = True
        if not _on:
            # off：仅大小保护（最低安全底线）
            if len(content) > 1_048_576:
                return content[:1_048_576] + "\n[TRUNCATED: 外部内容超 1MB]"
            return content
        _notes = []
        # ① 大小限制（<1MB）
        if len(content) > 1_048_576:
            content = content[:1_048_576]
            _notes.append("超1MB已截断")
        # ② 来源标注（防 repudiation——可溯源）
        content = f"[来源: {func_name} @ {time.strftime('%Y-%m-%d %H:%M:%S')}]\n" + content
        # ③ 格式校验（http 工具应含状态码——L2 修复 2026-08-18：正则匹配 HTTP/1.x 200 或 status 字段，
        #    避免纯 JSON/纯文本误报）
        if func_name in ("web_extract", "web_fetch", "fetch_url", "http_request", "curl"):
            _has_status = bool(
                re.search(r"HTTP/[12]\.\d\s+\d{3}", content[:2000])
                or re.search(r"""status[_ ]?code["']?\s*[:=]\s*\d{3}""", content[:2000])
            )
            if not _has_status:
                _notes.append("无 HTTP 状态信息")
        # ④ 敏感词/注入扫描
        _low = content.lower()
        # M2 修复（2026-08-18）：英文词用 \b 词边界（防 "you" 类误报）——中文保持 contains（.lower() 等价原串）
        def _hit(w: str) -> bool:
            # 词边界仅用于"纯字母单词"（you are now 等）——含符号/非字母结尾的模式（exec( 等）直接 contains
            if w.isascii() and w.isalpha():
                return re.search(r"\b" + re.escape(w.lower()) + r"\b", _low) is not None
            return w.lower() in _low
        _inject_hits = [w for w in self._INJECTION_PATTERNS if _hit(w)]
        _sens_hits = [w for w in self._SENSITIVE_PATTERNS if _hit(w)]
        if _inject_hits or _sens_hits:
            _flag = f"[SUSPECTED INJECTION: 注入词={_inject_hits[:3]} 敏感词={_sens_hits[:3]}]"
            _notes.append(_flag)
            logger.warning("HardRule#5: %s 外部内容含可疑模式 %s", func_name, _flag)
        if _notes:
            content = content + "\n[外部内容校验: " + "; ".join(_notes) + "]"
        # #5 第 3 层：上下文隔离（双重包裹——外部内容与系统/用户指令物理隔离）
        # L3 审计修复（2026-08-18）：内容内若含边界标记 → 转义（防边界错位/注入变体）
        content = content.replace("[EXTERNAL_DATA_END]", "[EXTERNAL_DATA_EOM]")
        content = content.replace("[EXTERNAL_DATA_START]", "[EXTERNAL_DATA_BOM]")
        content = "[EXTERNAL_DATA_START]\n" + content + "\n[EXTERNAL_DATA_END]"
        # #5 第 4 层：审计日志（外部流量记录——可溯源）
        # P3 修复（2026-08-18）：异步队列投递——磁盘慢/满不阻塞工具调用
        try:
            _start_audit_writer()
            _AUDIT_QUEUE.put(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {func_name} len={len(content)}"
                f" notes={';'.join(_notes) if _notes else 'clean'}\n",
                block=False,  # 队列满 → 丢弃（审计不阻塞主流程）
            )
        except Exception:
            pass  # 审计失败不阻塞
        return content

    # ── 架构硬规则 #1 阶段 1：路径白名单（2026-08-18 Hermes 执行 · OpenClaw security 方案）──
    # 文件操作工具（read/write/exec）路径分级：workspace 允许读写 / project 允许读 / 系统目录禁止。
    # env 门控 MIMIR_PATH_WHITELIST（默认 workspace,project；off 回全权限）
    _PATH_TOOLS = ("read_file", "write_file", "patch", "exec", "terminal", "bash", "list_dir")
    _DENY_PATH_FRAGMENTS = (
        "/etc/", "/usr/", "/bin/", "/sbin/", "/var/", "/root/", "/proc/", "/sys/",
        "/.ssh/", "/.aws/", "/.kube/", "/.gnupg/", "/.config/", "/.git/",
        "id_rsa", "id_ed25519", ".pem", ".key", "credentials", ".env",
    )

    def _validate_path_access(self, func_name: str, arguments: dict) -> Optional[str]:
        """路径白名单校验（#1 阶段 1 + 审计修复 S1/S2/S3/S4/L5/E2——2026-08-18 21:00）：
        ① unquote 解码（S3 URL 编码绕过）② normcase 统一大小写（S2）③ realpath 解析符号链接（S1）
        ④ DENY 永远生效（E2：off 仅解除分级，不解除禁止路径）⑤ kwargs 多参数名扫描（S4）
        ⑥ exec 无路径命令高危模式扫描（L5）
        """
        if func_name not in self._PATH_TOOLS:
            return None
        try:
            _enabled = os.environ.get("MIMIR_PATH_WHITELIST", "workspace,project").strip().lower()
            _whitelist_on = _enabled not in ("off", "0", "false", "no")
        except Exception:
            _whitelist_on = True
        # 提取路径（S4：多参数名扫描——不只 3 个固定 key）
        _path = ""
        if isinstance(arguments, dict):
            for _k in ("path", "cwd", "command", "script_path", "cmd", "bash_cmd", "shell_cmd", "workdir", "file_path"):
                _v = arguments.get(_k)
                if isinstance(_v, str) and _v.strip():
                    _path = _v
                    break
        if not _path:
            # L5：exec/terminal 无路径参数——高危命令模式扫描（阶段 1.5）
            if func_name in ("exec", "terminal", "bash"):
                _cmd = str(arguments.get("command") or arguments.get("cmd") or "")
                _low_cmd = _cmd.lower()
                for _d in ("rm -rf /", "rm -fr /", "dd if=/dev/zero", "mkfs", "> /dev/sda",
                           "chmod 777 /", "chown -r", ":(){", "shutdown",
                           "curl | bash", "curl|bash", "wget | bash", "wget|bash"):
                    if _d in _low_cmd:
                        logger.warning("HardRule#1: %s 高危命令被拒: %s", func_name, _cmd[:80])
                        return f"Blocked by path whitelist: dangerous command pattern '{_d}'"
            return None  # 真无路径（如 list_dir 无参）→ 放行
        # 路径规范化（S3 unquote → S2 normcase → S1 realpath）
        try:
            from urllib.parse import unquote
            _path_n = unquote(_path)
        except Exception:
            _path_n = _path
        _path_n = os.path.normcase(_path_n).lower()  # Linux normcase 不转小写——显式 lower（S2）
        try:
            _path_r = os.path.normpath(os.path.realpath(os.path.expanduser(_path_n))).lower()  # normpath 消 ..（S3）+ realpath（S1）
        except Exception:
            _path_r = _path_n
        # DENY 检查（永远生效——E2：off 仅解除分级，不解除禁止路径）
        for _frag in self._DENY_PATH_FRAGMENTS:
            if _frag in _path_r or _frag in _path_n:
                logger.warning("HardRule#1: %s 访问被拒路径 %s (fragment=%s)", func_name, _path[:80], _frag)
                return f"Blocked by path whitelist: '{_path[:80]}' contains denied path segment '{_frag}'"
        if not _whitelist_on:
            return None  # 白名单分级关闭（DENY 已查）→ 放行
        # 白名单分级（workspace 允许读写 / project 只读）
        _home = os.path.expanduser("~")
        _allowed_rw = (_home + "/.mimiraether", _home + "/wiki", _home + "/.openclaw/workspace")
        _allowed_r = (_home + "/src/MimirAether",)
        _p = os.path.abspath(_path_r)
        for _a in _allowed_rw:
            if _p.startswith(os.path.normcase(os.path.abspath(_a)).lower()):
                return None
        for _a in _allowed_r:
            if _p.startswith(os.path.normcase(os.path.abspath(_a)).lower()):
                if func_name in ("write_file", "patch"):
                    return f"Blocked by path whitelist: '{_path[:80]}' is read-only (project dir)"
                return None
        # 白名单外路径（保守拒绝——/tmp 例外）
        if _p.startswith(os.path.normcase("/tmp/")):
            return None
        logger.warning("HardRule#1: %s 访问白名单外路径 %s", func_name, _path[:80])
        return f"Blocked by path whitelist: '{_path[:80]}' outside allowed paths"

    async def _execute_single_tool(self, tool_call: Dict, turn: int = 0) -> ToolResult:
        """
        执行单个工具调用
        
        学习自Hermes _execute_single_tool：
        - 收集ToolError实例用于元数据
        - 支持turn参数用于错误追踪
        
        Args:
            tool_call: 工具调用
            turn: 当前轮次(用于错误记录)
        """
        # 获取tool_call的id
        tool_call_id = _get_tool_id(tool_call) or "unknown"

        # 处理OpenAI格式:{type: 'function', function: {name, arguments}}
        if tool_call.get("type") == "function" and "function" in tool_call:
            func_name = tool_call["function"].get("name", "")
            raw_args = tool_call["function"].get("arguments", {})
        else:
            # 兼容旧格式
            func_name = tool_call.get("name", "")
            raw_args = tool_call.get("arguments", {})

        # pre_tool_call hook 已移除(从VALID_HOOKS中删除)- 曾导致无限循环bug

        # 触发tool_start_callback
        if self.tool_start_callback:
            try:
                args_preview = json.dumps(raw_args)[:200] if raw_args else "{}"
                self.tool_start_callback(func_name, args_preview)
            except Exception as e:
                logger.warning(f"tool_start_callback error: {e}")

        # 校验必需字段
        if not tool_call_id or tool_call_id == "unknown":
            logger.warning(f"SKIP tool_call: missing 'id' field: {tool_call}")
            # Hermes风格:收集ToolError
            self._tool_errors.append(ToolError(
                turn=turn,
                tool_name=func_name or "unknown",
                arguments=str(raw_args)[:200],
                error="Missing tool_call id field",
                tool_result="Error: tool_call missing 'id' field",
            ))
            return ToolResult(
                tool_call_id="unknown",
                content="Error: tool_call missing 'id' field",
                is_error=True
            )
        if not func_name:
            logger.warning(f"SKIP tool_call: missing 'name' field: {tool_call}")
            # Hermes风格:收集ToolError
            self._tool_errors.append(ToolError(
                turn=turn,
                tool_name="unknown",
                arguments=str(raw_args)[:200],
                error="Missing tool_call name field",
                tool_result="Error: tool_call missing 'name' field",
            ))
            return ToolResult(
                tool_call_id=tool_call_id,
                content="Error: tool_call missing 'name' field",
                is_error=True
            )

        try:
            # P0-1: 统一参数修复 → agent/tools/repair.py
            from .tools.repair import repair_tool_arguments
            arguments = repair_tool_arguments(func_name, raw_args)

            # 架构硬规则 #1 阶段 1：路径白名单（文件操作工具）
            _path_err = self._validate_path_access(func_name, arguments)
            if _path_err:
                self._tool_errors.append(ToolError(
                    turn=turn, tool_name=func_name, arguments=str(raw_args)[:200],
                    error=_path_err, tool_result=f"Error: {_path_err}",
                ))
                return ToolResult(tool_call_id=tool_call_id, content=f"Error: {_path_err}", is_error=True)
            
            # write_file 修复失败 → 返回错误
            if func_name == "write_file" and isinstance(arguments, dict) and "path" not in arguments:
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error="write_file needs path and content",
                    tool_result="Error: write_file requires path and content in JSON format",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content="Error: write_file requires path and content in JSON format",
                    is_error=True
                )
            # P0-1: arguments 已在 repair_tool_arguments 中标准化为 dict
            if not isinstance(arguments, dict):
                logger.warning(f"Arguments is not a dict for tool {func_name}: {type(arguments)}")
                # Hermes风格:收集ToolError
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error=f"TypeError: arguments must be dict, got {type(arguments).__name__}",
                    tool_result="Error: arguments must be a dict",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content="Error: arguments must be a dict",
                    is_error=True
                )

            # Strategy layer: pre-validate + remap deprecated names (e.g. search_web → web_search)
            from tools.strategy import pre_validate_tool_call, route_tool_call

            pre_result = pre_validate_tool_call(func_name, arguments)
            if not pre_result.ok:
                err_msg = pre_result.error_message or "pre_validation failed"
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error=err_msg,
                    tool_result=f"Error: {err_msg}",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"Error: {err_msg}",
                    is_error=True,
                )

            func_name, arguments, routing_error = route_tool_call(func_name, arguments)
            if routing_error:
                self._tool_errors.append(ToolError(
                    turn=turn,
                    tool_name=func_name,
                    arguments=str(raw_args)[:200],
                    error=routing_error,
                    tool_result=f"Error: {routing_error}",
                ))
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content=f"Error: {routing_error}",
                    is_error=True,
                )

            # 类型强制：LLM常见类型不匹配 → 强制对齐JSON Schema
            from model_tools import coerce_tool_args
            arguments = coerce_tool_args(func_name, arguments)

            from agent.tool_call_cache import get_cached, set_cached, should_cache_tool

            if should_cache_tool(func_name):
                cached = get_cached(func_name, arguments)
                if cached is not None:
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        content="[cached read-only result]\n" + cached,
                        is_error=False,
                    )

            # ── self_evolution IC 安全门 ──
            # 轻量级：只查 PROTECTED_FILES（不初始化引擎、不做AST解析），
            # 每次工具调用 <1ms。完整 pre_action_check 留给 evolution_guard。
            if func_name in ("write_file", "patch", "skill_manage"):
                target_path = arguments.get("path") or arguments.get("name", "")
                if target_path and ("agent/" in target_path or "gateway/" in target_path):
                    try:
                        from agent.self_evolution.state_encoder import PROTECTED_FILES
                        fname = target_path.rsplit("/", 1)[-1]
                        for group, files in PROTECTED_FILES.items():
                            if fname in files:
                                self._tool_errors.append(ToolError(
                                    turn=turn,
                                    tool_name=func_name,
                                    arguments=str(raw_args)[:200],
                                    error=f"IC constraint [{group}]: {target_path}",
                                    tool_result=f"Blocked: '{target_path}' is a protected file",
                                ))
                                # ── IC 顾问：不只说 no，还提供替代方案（EV-VOE08） ──
                                advice_msg = ""
                                try:
                                    from agent.self_evolution.engine import ic_advisor
                                    advice = ic_advisor(target_path)
                                    if advice["alternatives"]:
                                        alts = "; ".join(
                                            f"'{a['file']}' (TC={a['tc']}, 影响面={a['blast_radius']})"
                                            for a in advice["alternatives"][:3]
                                        )
                                        advice_msg = f" | 💡 建议: {alts}"
                                except Exception:
                                    pass  # 顾问失败不阻塞拦截

                                return ToolResult(
                                    tool_call_id=tool_call_id,
                                    content=f"Blocked by self_evolution [{group}]: "
                                            f"'{target_path}' is a protected file{advice_msg}",
                                    is_error=True,
                                )
                    except ImportError:
                        pass  # fail-open: self_evolution 模块不存在时静默跳过
                    except Exception as e:
                        logger.warning(f"self_evolution IC gate error: {e}")  # fail-open

                # ── VoE soft channel (EV-VOE04) ──
                # 只记录不改行为：IC 硬拦截之后，VoE 评估"这个改动是否异常"
                # 异常不硬拦截，仅 log WARNING 供后续审查
                try:
                    from agent.self_evolution.voe_detector import VoEDetector
                    _voe = VoEDetector()  # 无历史 → 无惊讶（fail-open）
                    _r = _voe.detect([target_path])
                    if _r["level"] in ("caution", "unusual"):
                        logger.warning(
                            f"VoE [{_r['level']}] file={target_path} "
                            f"surprise={_r['surprise_score']} reasons={_r['reasons']}"
                        )
                except ImportError:
                    pass  # voe_detector 不存在 → 静默跳过
                except Exception:
                    pass  # VoE 任何异常 → 不阻塞

            # ── 统一 dispatch：通过 tools.registry.registry.dispatch() ──
            # dispatch() 返回 JSON 字符串，统一处理错误格式。
            # Sync handler 在线程池中运行以避免阻塞 event loop。
            # parent_agent=self 通过 partial 绑定，避免 run_in_executor 不支持 kwargs。
            entry = _tool_registry_module.registry._tools.get(func_name)
            if entry is not None and not entry.is_async:
                _dispatch_bound = functools.partial(
                    _tool_registry_module.registry.dispatch,
                    func_name, arguments,
                    parent_agent=self,
                )
                result = await asyncio.get_running_loop().run_in_executor(
                    _tool_executor,
                    _dispatch_bound,
                )
            else:
                result = _tool_registry_module.registry.dispatch(func_name, arguments, parent_agent=self)

            # Plugin hook: post_tool_call
            # 在工具调用后执行
            try:
                self._invoke_hook(
                    "post_tool_call",
                    tool_name=func_name,
                    result=str(result),
                )
            except Exception as e:
                logger.warning(f"post_tool_call hook failed: {e}")

            # 触发tool_complete_callback
            if self.tool_complete_callback:
                try:
                    self.tool_complete_callback(func_name, str(result))
                except Exception as e:
                    logger.warning(f"tool_complete_callback error: {e}")

            # 软心跳记录
            try:
                import subprocess, os, time
                _start = getattr(self, '_tool_start_time', {}).pop(func_name, time.time())
                _dur = (time.time() - _start) * 1000
                _hb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'heartbeat', 'soft_beat.py')
                subprocess.Popen([sys.executable, _hb_path, func_name, str(_dur), 'OK'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            content = str(result)
            # 架构硬规则 #5 第 1 层：外部内容校验（收口统一出口）
            content = self._validate_external_content(func_name, content)
            if should_cache_tool(func_name):
                set_cached(func_name, arguments, content)
            tracker = getattr(self, "_subdirectory_hints", None)
            if tracker is not None:
                hints = tracker.check_tool_call(func_name, arguments)
                if hints:
                    content = content + "\n\n" + hints

            return ToolResult(
                tool_call_id=tool_call_id,
                content=content,
                is_error=False
            )
        except Exception as e:
            logger.error("Tool execution failed: %s, error: %s", func_name or "unknown", e)
            # Hermes风格:收集ToolError
            self._tool_errors.append(ToolError(
                turn=turn,
                tool_name=func_name,
                arguments=str(raw_args)[:200],
                error=f"{type(e).__name__}: {e}",
                tool_result="Error: tool execution failed",
            ))

            # 触发tool_complete_callback(错误情况)
            if self.tool_complete_callback:
                try:
                    self.tool_complete_callback(func_name, f"Error: {e}")
                except Exception:
                    pass

            # 软心跳记录(错误)
            try:
                import subprocess, os, time
                _start = getattr(self, '_tool_start_time', {}).pop(func_name, time.time())
                _dur = (time.time() - _start) * 1000
                _hb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'heartbeat', 'soft_beat.py')
                subprocess.Popen([sys.executable, _hb_path, func_name, str(_dur), 'FAIL', str(e)[:100]], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            return ToolResult(
                tool_call_id=tool_call["id"],
                content="Error: tool execution failed",
                is_error=True
            )


